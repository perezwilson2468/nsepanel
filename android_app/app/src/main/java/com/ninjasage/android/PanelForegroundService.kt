package com.ninjasage.android

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.os.Build
import android.os.IBinder
import android.os.PowerManager
import androidx.core.app.NotificationCompat
import androidx.core.content.ContextCompat
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.cancel
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import com.theforgotten.nsepanel.R

class PanelForegroundService : Service() {
    private val serviceJob = Job()
    private val serviceScope = CoroutineScope(serviceJob + Dispatchers.IO)
    private val bridge by lazy { PythonBridge(applicationContext) }
    private val billingRepository by lazy { BillingTimeRepository(applicationContext) }
    private var notificationJob: Job? = null
    private var billingRefreshTick = 0
    private var wakeLock: PowerManager.WakeLock? = null

    override fun onCreate() {
        super.onCreate()
        createNotificationChannel()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_START, null -> {
                ensureWakeLock()
                startForeground(NOTIFICATION_ID, buildNotification("NSe Panel active", "Keeping your session alive"))
                startNotificationLoop()
            }
        }
        return START_STICKY
    }

    override fun onDestroy() {
        notificationJob?.cancel()
        serviceJob.cancel()
        serviceScope.cancel()
        releaseWakeLock()
        super.onDestroy()
    }

    override fun onBind(intent: Intent?): IBinder? = null

    private fun startNotificationLoop() {
        if (notificationJob?.isActive == true) return
        notificationJob = serviceScope.launch {
            while (isActive) {
                val state = bridge.call("get_state")
                billingRefreshTick += 1
                val billingSnapshot = if (billingRefreshTick % 1800 == 0) {
                    billingRepository.refresh()
                } else {
                    billingRepository.snapshotNow()
                }

                if (!billingSnapshot.hasAccess && state.optBoolean("running")) {
                    bridge.call("stop_action")
                }

                val title: String
                val text: String
                if (state.optBoolean("success")) {
                    val runningAction = state.optString("running_action")
                    val username = state.optString("username").ifBlank { "No account" }
                    val character = state.optJSONObject("character")
                    val characterName = character?.optString("name").orEmpty().ifBlank { "No character selected" }
                    val currentProfile = state.optJSONObject("current_amf_profile")
                    val serverLabel = currentProfile?.optString("label").orEmpty().ifBlank { "Unknown server" }
                    if (!billingSnapshot.hasAccess) {
                        title = "Billing expired"
                        text = "$serverLabel - actions locked"
                    } else if (runningAction.isNotBlank() && runningAction != "null") {
                        title = "Action running: $runningAction"
                        text = "$serverLabel - $username - $characterName"
                    } else {
                        title = "NSe Panel active"
                        text = "$serverLabel - $username - $characterName"
                    }
                } else {
                    title = "NSe Panel active"
                    text = state.optString("message", "Background service running")
                }

                val manager = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
                manager.notify(NOTIFICATION_ID, buildNotification(title, text))
                delay(2000)
            }
        }
    }

    private fun buildNotification(title: String, text: String) =
        NotificationCompat.Builder(this, CHANNEL_ID)
            .setSmallIcon(R.mipmap.ic_launcher)
            .setContentTitle(title)
            .setContentText(text)
            .setContentIntent(
                PendingIntent.getActivity(
                    this,
                    0,
                    Intent(this, MainActivity::class.java).apply {
                        flags = Intent.FLAG_ACTIVITY_SINGLE_TOP or Intent.FLAG_ACTIVITY_CLEAR_TOP
                    },
                    PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
                ),
            )
            .setOngoing(true)
            .setOnlyAlertOnce(true)
            .setSilent(true)
            .build()

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
        val manager = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        val channel = NotificationChannel(
            CHANNEL_ID,
            "NSe Panel Background",
            NotificationManager.IMPORTANCE_LOW,
        ).apply {
            description = "Keeps NSe Panel running while the app is in the background"
        }
        manager.createNotificationChannel(channel)
    }

    private fun ensureWakeLock() {
        val current = wakeLock
        if (current?.isHeld == true) return
        val powerManager = getSystemService(Context.POWER_SERVICE) as? PowerManager ?: return
        wakeLock = (current ?: powerManager.newWakeLock(
            PowerManager.PARTIAL_WAKE_LOCK,
            "$packageName:panel-foreground",
        ).apply {
            setReferenceCounted(false)
        }).also {
            if (!it.isHeld) {
                it.acquire()
            }
        }
    }

    private fun releaseWakeLock() {
        val current = wakeLock ?: return
        if (current.isHeld) {
            current.release()
        }
        wakeLock = null
    }

    companion object {
        private const val CHANNEL_ID = "nse_panel_background"
        private const val NOTIFICATION_ID = 1001
        private const val ACTION_START = "com.ninjasage.android.action.START_BACKGROUND"

        fun start(context: Context) {
            val intent = Intent(context, PanelForegroundService::class.java).apply {
                action = ACTION_START
            }
            ContextCompat.startForegroundService(context, intent)
        }

        fun stop(context: Context) {
            context.stopService(Intent(context, PanelForegroundService::class.java))
        }
    }
}
