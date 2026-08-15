package com.ninjasage.android

import android.Manifest
import android.app.Activity
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.SystemClock
import android.util.Base64
import android.util.Log
import android.view.ViewGroup
import android.webkit.CookieManager
import android.webkit.JavascriptInterface
import android.webkit.WebChromeClient
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.FrameLayout
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.viewModels
import androidx.core.content.ContextCompat
import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.defaultMinSize
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Surface
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Checkbox
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ElevatedCard
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ExposedDropdownMenuBox
import androidx.compose.material3.ExposedDropdownMenuDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Scaffold
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.TextButton
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalLifecycleOwner
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.style.TextDecoration
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import java.io.BufferedReader
import java.text.SimpleDateFormat
import java.net.URLDecoder
import java.util.Date
import java.util.Locale
import java.util.concurrent.TimeUnit
import org.json.JSONObject
import com.theforgotten.nsepanel.R
import com.theforgotten.nsepanel.BuildConfig

class MainActivity : ComponentActivity() {
    companion object {
        @Volatile
        var isVisible: Boolean = false
            private set

        private var lastBackgroundedAtElapsed: Long = 0L
        private const val APP_OPEN_BACKGROUND_THRESHOLD_MS = 1_500L
    }

    private val viewModel by viewModels<AppViewModel>()
    private val notificationPermissionLauncher =
        registerForActivityResult(ActivityResultContracts.RequestPermission()) { }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        requestNotificationPermissionIfNeeded()
        enableEdgeToEdge()
        setContent {
            val uiState by viewModel.uiState.collectAsState()
            MaterialTheme(
                colorScheme = darkColorScheme(
                    primary = Color(0xFFE1A44A),
                    secondary = Color(0xFFFFC978),
                    background = Color(0xFF090909),
                    surface = Color(0xFF121212),
                    onPrimary = Color(0xFF16120C),
                    onSecondary = Color(0xFF16120C),
                    onBackground = Color.White,
                    onSurface = Color.White,
                ),
            ) {
                NinjaSageApp(
                    uiState = uiState,
                    viewModel = viewModel,
                    onAddTimeClick = { },
                    rewardedButtonLabel = "",
                    rewardedButtonEnabled = false,
                )
            }
        }
    }

    override fun onStart() {
        super.onStart()
        isVisible = true
        viewModel.onAppForegrounded()
        val backgroundGapMs = if (lastBackgroundedAtElapsed == 0L) Long.MAX_VALUE else {
            SystemClock.elapsedRealtime() - lastBackgroundedAtElapsed
        }
    }

    override fun onStop() {
        isVisible = false
        lastBackgroundedAtElapsed = SystemClock.elapsedRealtime()
        super.onStop()
    }

    private fun requestNotificationPermissionIfNeeded() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU) return
        if (
            ContextCompat.checkSelfPermission(
                this,
                Manifest.permission.POST_NOTIFICATIONS,
            ) == PackageManager.PERMISSION_GRANTED
        ) {
            return
        }
        notificationPermissionLauncher.launch(Manifest.permission.POST_NOTIFICATIONS)
    }
}

private data class NinjaSagaWebAuthPayload(
    val fbUid: String,
    val fbName: String,
    val fbAt: String,
    val fbSig: String,
    val hashTime: String,
    val time: Int = 0,
)

private data class NinjaSagaEmulatorContext(
    val hashTime: String,
    val time: Int = 0,
)

private data class NinjaSagaPartialAuth(
    val fbUid: String,
    val fbName: String,
    val fbAt: String,
    val fbSig: String,
)

private data class NinjaSagaNsDirective(
    val action: String,
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun NinjaSageApp(
    uiState: UiState,
    viewModel: AppViewModel,
    onAddTimeClick: () -> Unit,
    rewardedButtonLabel: String,
    rewardedButtonEnabled: Boolean,
) {
    val context = LocalContext.current
    val discordInvite = stringResource(R.string.discord_invite)
    val startupPhaseActive = !uiState.versionChecked || !uiState.startupReady
    val hasAccountContext = uiState.character != null || uiState.characters.isNotEmpty()
    var showBillingLogin by rememberSaveable { mutableStateOf(false) }
        showBillingLogin = false
    if (startupPhaseActive) {
        StartupSplashScreen(uiState)
        return
    }
    Scaffold(
        containerColor = Color.Transparent,
        topBar = {
            TopAppBar(
                title = {
                    Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
                        Text(stringResource(R.string.app_name), color = Color.White)
                        if (uiState.billingSubscriptionActive && uiState.billingUsername != null) {
                            Text(
                                text = buildBillingHeaderDetail(uiState),
                                color = if (uiState.billingSubscriptionActive) Color(0xFFA5D6A7) else Color(0xFFFFCC80),
                                style = MaterialTheme.typography.labelMedium,
                            )
                        } else if (hasAccountContext) {
                            Text(
                                text = formatBillingRemaining(uiState.billingRemainingMillis),
                                color = if (uiState.hasBillingAccess) Color(0xFFA5D6A7) else Color(0xFFFFCC80),
                                style = MaterialTheme.typography.labelMedium,
                            )
                        }
                    }
                },
                actions = {
                    OutlinedButton(
                        onClick = { showBillingLogin = true },
                        enabled = !uiState.billingChecking,
                        modifier = Modifier
                            .padding(end = 8.dp)
                            .defaultMinSize(minHeight = 36.dp),
                        colors = ButtonDefaults.outlinedButtonColors(
                            containerColor = Color(0xFF191919),
                            contentColor = if (uiState.billingSubscriptionActive) Color(0xFFA5D6A7) else Color(0xFFFFC978),
                        ),
                    ) {
                        Text(uiState.billingUsername ?: "Login")
                    }
                    if (hasAccountContext) {
                        if (!BuildConfig.DISABLE_ADS && !uiState.billingDisableAds) {
                            OutlinedButton(
                                onClick = onAddTimeClick,
                                enabled = rewardedButtonEnabled,
                                modifier = Modifier
                                    .padding(end = 8.dp)
                                    .defaultMinSize(minHeight = 36.dp),
                                colors = ButtonDefaults.outlinedButtonColors(
                                    containerColor = Color(0xFF191919),
                                    contentColor = Color(0xFFFFC978),
                                ),
                            ) {
                                Text(if (rewardedButtonEnabled) "+Time" else "Loading Ad")
                            }
                        }
                    }
                    IconButton(
                        onClick = {
                            context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(discordInvite)))
                        },
                        modifier = Modifier
                            .padding(end = 8.dp)
                            .size(40.dp),
                    ) {
                        Icon(
                            painter = painterResource(R.drawable.ic_discord),
                            contentDescription = stringResource(R.string.discord_label),
                            modifier = Modifier.size(22.dp),
                            tint = Color.Unspecified,
                        )
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = Color(0xFF090909),
                    titleContentColor = Color.White,
                    actionIconContentColor = Color(0xFFCED8FF),
                ),
            )
        },
    ) { padding ->
        Box(
            modifier = Modifier
                .fillMaxSize()
                .background(
                    Brush.verticalGradient(
                        colors = listOf(Color(0xFF1A1A1A), Color(0xFF341515), Color(0xFF090909)),
                    ),
                )
                .padding(padding),
        ) {
            if (uiState.character == null) {
                LoginAndCharacterScreen(uiState, viewModel)
            } else {
                DashboardScreen(
                    uiState = uiState,
                    viewModel = viewModel,
                    onAddTimeClick = onAddTimeClick,
                    rewardedButtonLabel = rewardedButtonLabel,
                    rewardedButtonEnabled = rewardedButtonEnabled,
                )
            }

            if (uiState.isBusy) {
                Box(
                    modifier = Modifier
                        .fillMaxSize()
                        .background(Color(0x66000000)),
                    contentAlignment = Alignment.Center,
                ) {
                    CircularProgressIndicator()
                }
            }

            if (uiState.showNinjaSagaWebLogin) {
                NinjaSagaWebLoginOverlay(
                    onDismiss = viewModel::closeNinjaSagaWebLogin,
                    onWebAuthCaptured = { payload ->
                        viewModel.loginWithNinjaSagaWebAuth(
                            payload.fbUid,
                            payload.fbName,
                            payload.fbAt,
                            payload.fbSig,
                            payload.hashTime,
                            payload.time,
                            currentNinjaSagaCookieHeader(),
                        )
                    },
                )
            }

            if (uiState.clanWarPanel.showing && !uiState.clanWarCaptcha.required) {
                NinjaSagaClanWarPanelOverlay(
                    uiState = uiState,
                    viewModel = viewModel,
                )
            }

            if (uiState.clanWarCaptcha.required) {
                NinjaSagaClanWarCaptchaOverlay(
                    uiState = uiState,
                    viewModel = viewModel,
                )
            }

            if (showBillingLogin) {
                BillingLoginDialog(
                    uiState = uiState,
                    onDismiss = { showBillingLogin = false },
                    onLogin = { username, password -> viewModel.loginBilling(username, password) },
                    onRefresh = { viewModel.refreshBillingStatus(showChecking = true) },
                    onLogout = {
                        viewModel.logoutBilling()
                        showBillingLogin = false
                    },
                )
            }



            uiState.serverVersionDialogMessage?.let { dialogMessage ->
                AlertDialog(
                    onDismissRequest = viewModel::dismissServerVersionDialog,
                    title = { Text("Panel Outdated", color = Color.White) },
                    text = { Text(dialogMessage, color = Color(0xFFE0D0B8)) },
                    confirmButton = {
                        Button(onClick = viewModel::dismissServerVersionDialog) {
                            Text("OK")
                        }
                    },
                    containerColor = Color(0xFF18120F),
                    titleContentColor = Color.White,
                    textContentColor = Color(0xFFE0D0B8),
                )
            }
        }
    }
}

@Composable
private fun BillingLoginDialog(
    uiState: UiState,
    onDismiss: () -> Unit,
    onLogin: (String, String) -> Unit,
    onRefresh: () -> Unit,
    onLogout: () -> Unit,
) {
    val context = LocalContext.current
    val openedWithAccount = remember { uiState.billingUsername != null }
    var username by rememberSaveable(uiState.billingUsername) { mutableStateOf(uiState.billingUsername.orEmpty()) }
    var password by rememberSaveable { mutableStateOf("") }
    var showPassword by rememberSaveable { mutableStateOf(false) }
    val hasBillingAccount = uiState.billingUsername != null

    LaunchedEffect(uiState.billingUsername, uiState.billingChecking) {
        if (!openedWithAccount && uiState.billingUsername != null && !uiState.billingChecking) {
            onDismiss()
        }
    }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(if (hasBillingAccount) "Subscription Account" else "Subscription Login", color = Color.White) },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                if (hasBillingAccount) {
                    Text(uiState.billingUsername.orEmpty(), color = Color.White, style = MaterialTheme.typography.titleMedium)
                    Text(
                        if (uiState.billingSubscriptionActive) {
                            "Active subscription. ${formatBillingDateTime(uiState.billingExpiryMillis)}. Expired"
                        } else {
                            "No active subscription. Android free mode still works with ads and local +Time billing."
                        },
                        color = Color(0xFFE0D0B8),
                    )
                    Text(
                        "Buy or extend your subscription in the web panel.",
                        color = Color(0xFFFFCC80),
                    )
                } else {
                    Text(
                        "Login with your panel account. If you do not have an active subscription, Android stays in free mode with ads and +Time.",
                        color = Color(0xFFE0D0B8),
                    )
                    OutlinedTextField(
                        value = username,
                        onValueChange = { username = it },
                        label = { Text("Username") },
                        singleLine = true,
                        enabled = !uiState.billingChecking,
                        modifier = Modifier.fillMaxWidth(),
                    )
                    OutlinedTextField(
                        value = password,
                        onValueChange = { password = it },
                        label = { Text("Password") },
                        visualTransformation = if (showPassword) VisualTransformation.None else PasswordVisualTransformation(),
                        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password),
                        trailingIcon = {
                            TextButton(onClick = { showPassword = !showPassword }, enabled = !uiState.billingChecking) {
                                Text(if (showPassword) "Hide" else "Show")
                            }
                        },
                        singleLine = true,
                        enabled = !uiState.billingChecking,
                        modifier = Modifier.fillMaxWidth(),
                    )
                }
            }
        },
        confirmButton = {
            if (hasBillingAccount) {
                Button(
                    onClick = {
                        context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse("https://example.com")))
                    },
                ) {
                    Text("Buy Subscription")
                }
            } else {
                Button(
                    onClick = { onLogin(username.trim(), password) },
                    enabled = username.isNotBlank() && password.isNotBlank() && !uiState.billingChecking,
                ) {
                    if (uiState.billingChecking) {
                        CircularProgressIndicator(
                            modifier = Modifier
                                .padding(end = 8.dp)
                                .size(16.dp),
                            strokeWidth = 2.dp,
                            color = Color.White,
                        )
                    }
                    Text(if (uiState.billingChecking) "Checking..." else "Login")
                }
            }
        },
        dismissButton = {
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                if (hasBillingAccount) {
                    OutlinedButton(
                        onClick = onRefresh,
                        enabled = !uiState.billingChecking,
                    ) {
                        Text(if (uiState.billingChecking) "Refreshing..." else "Refresh")
                    }
                    OutlinedButton(onClick = onLogout) {
                        Text("Logout")
                    }
                }
                OutlinedButton(onClick = onDismiss) {
                    Text("Close")
                }
            }
        },
        containerColor = Color(0xFF18120F),
        titleContentColor = Color.White,
        textContentColor = Color(0xFFE0D0B8),
    )
}

@Composable
private fun LoginAndCharacterScreen(uiState: UiState, viewModel: AppViewModel) {
    var showPassword by rememberSaveable { mutableStateOf(false) }
    var riftVerificationCode by rememberSaveable { mutableStateOf("") }
    val fieldColors = OutlinedTextFieldDefaults.colors(
        focusedTextColor = Color.White,
        unfocusedTextColor = Color(0xFFF1E9DD),
        focusedBorderColor = Color(0xFFE1A44A),
        unfocusedBorderColor = Color(0xFF8F6C3C),
        focusedLabelColor = Color(0xFFFFC978),
        unfocusedLabelColor = Color(0xFFD3BE9A),
        cursorColor = Color(0xFFFFC978),
    )

    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        LaunchedEffect(uiState.riftVerification.required) {
            if (!uiState.riftVerification.required) {
                riftVerificationCode = ""
            }
        }
        if (uiState.showBaseGameSelection) {
            BaseGameSelectionScreen(uiState, viewModel)
            return@Column
        }
        if (uiState.showServerSelection) {
            AmfSelectionScreen(uiState, viewModel)
            return@Column
        }
        if (uiState.characters.isEmpty()) {
            ElevatedCard(colors = CardDefaults.elevatedCardColors(containerColor = Color(0xFF15110F))) {
                Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                    Text("Account Login", style = MaterialTheme.typography.headlineSmall, color = Color.White)
                    OutlinedButton(
                        onClick = viewModel::openBaseGameSelection,
                        modifier = Modifier.defaultMinSize(minHeight = 38.dp),
                    ) {
                        Text("Change Base Game / Server")
                    }
                    if (!uiState.serverVersionCompatible) {
                        Text(
                            text = uiState.statusMessage ?: "Panel outdated for this server.",
                            color = Color(0xFFFFCC80),
                            style = MaterialTheme.typography.bodyMedium,
                        )
                    }
                    if (uiState.currentBaseGame?.id == "rift" && uiState.riftVerification.required) {
                        Text(
                            text = uiState.riftVerification.message.ifBlank { "Enter the verification code sent to your email." },
                            color = Color(0xFFFFCC80),
                            style = MaterialTheme.typography.bodyMedium,
                        )
                        OutlinedTextField(
                            value = riftVerificationCode,
                            onValueChange = { riftVerificationCode = it },
                            modifier = Modifier.fillMaxWidth(),
                            label = { Text("Verification Code") },
                            colors = fieldColors,
                            singleLine = true,
                        )
                        Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                            Button(
                                onClick = { viewModel.verifyRiftCode(riftVerificationCode) },
                                modifier = Modifier.weight(1f),
                                enabled = riftVerificationCode.isNotBlank(),
                            ) {
                                Text("Verify Code")
                            }
                            OutlinedButton(
                                onClick = {
                                    riftVerificationCode = ""
                                    viewModel.changeCharacter()
                                },
                                modifier = Modifier.weight(1f),
                            ) {
                                Text("Back")
                            }
                        }
                    } else {
                        OutlinedTextField(
                            value = uiState.username,
                            onValueChange = viewModel::updateUsername,
                            modifier = Modifier.fillMaxWidth(),
                            label = { Text("Username") },
                            colors = fieldColors,
                            singleLine = true,
                        )
                        OutlinedTextField(
                            value = uiState.password,
                            onValueChange = viewModel::updatePassword,
                            modifier = Modifier.fillMaxWidth(),
                            label = { Text("Password") },
                            visualTransformation = if (showPassword) VisualTransformation.None else PasswordVisualTransformation(),
                            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password),
                            trailingIcon = {
                                TextButton(onClick = { showPassword = !showPassword }) {
                                    Text(if (showPassword) "Hide" else "Show")
                                }
                            },
                            colors = fieldColors,
                            singleLine = true,
                        )
                        Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                            Button(
                                onClick = viewModel::login,
                                modifier = Modifier.weight(1f),
                                enabled = uiState.serverVersionCompatible,
                            ) {
                                Text("Login")
                            }
                            OutlinedButton(
                                onClick = viewModel::quickLogin,
                                modifier = Modifier.weight(1f),
                                enabled = uiState.hasQuickLogin && uiState.serverVersionCompatible,
                            ) {
                                Text("Quick Login")
                            }
                        }
                    }
                    if (uiState.currentBaseGame?.id == "ninjasaga" || uiState.currentBaseGame?.id == "zenshin") {
                        Text(
                            text = if (uiState.currentBaseGame?.id == "zenshin") {
                                "Ninja Zenshin panel is experimental, please report bug!"
                            } else {
                                "NinjaSaga panel still in development, please report bug!"
                            },
                            color = Color(0xFFD3BE9A),
                            style = MaterialTheme.typography.bodySmall,
                        )
                    }
                }
            }
        } else {
            CharacterChooser(uiState, viewModel)
        }

        if (uiState.logs.isNotEmpty() || uiState.statusMessage != null) {
            LogPanel(uiState, viewModel)
        }


    }
}

@Composable
private fun NinjaSagaWebLoginOverlay(
    onDismiss: () -> Unit,
    onWebAuthCaptured: (NinjaSagaWebAuthPayload) -> Unit,
) {
    Card(
        modifier = Modifier
            .fillMaxSize()
            .padding(12.dp),
        colors = CardDefaults.cardColors(containerColor = Color(0xFF0D0D0D)),
    ) {
        Column(
            modifier = Modifier.fillMaxSize(),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 12.dp, vertical = 10.dp),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Column(modifier = Modifier.weight(1f)) {
                    Text("NinjaSaga Web Login", color = Color.White, style = MaterialTheme.typography.titleMedium)
                    Text(
                        "Log in on the official site. We will capture the emulator session automatically.",
                        color = Color(0xFFE0D0B8),
                        style = MaterialTheme.typography.bodySmall,
                    )
                }
                OutlinedButton(onClick = onDismiss) {
                    Text("Close")
                }
            }
            AndroidView(
                modifier = Modifier.fillMaxSize(),
                factory = { context ->
                    WebView(context).apply {
                        var authHandled = false
                        var lastEmulatorContext: NinjaSagaEmulatorContext? = null
                        var pendingPartialAuth: NinjaSagaPartialAuth? = null
                        layoutParams = FrameLayout.LayoutParams(
                            ViewGroup.LayoutParams.MATCH_PARENT,
                            ViewGroup.LayoutParams.MATCH_PARENT,
                        )
                        CookieManager.getInstance().setAcceptCookie(true)
                        CookieManager.getInstance().setAcceptThirdPartyCookies(this, true)
                        settings.javaScriptEnabled = true
                        settings.domStorageEnabled = true
                        settings.databaseEnabled = true
                        settings.javaScriptCanOpenWindowsAutomatically = true
                        settings.setSupportMultipleWindows(true)
                        settings.loadsImagesAutomatically = true
                        settings.mediaPlaybackRequiresUserGesture = false
                        settings.userAgentString =
                            "Mozilla/5.0 (Linux; Android 13; SM-G998B) AppleWebKit/537.36 " +
                            "(KHTML, like Gecko) Chrome/146.0.0.0 Mobile Safari/537.36"
                        webChromeClient = WebChromeClient()
                        webViewClient = object : WebViewClient() {
                            private fun tryHandle(url: String?): Boolean {
                                if (authHandled) return true
                                val raw = url.orEmpty()
                                parseNinjaSagaNsDirective(raw)?.let { directive ->
                                    when (directive.action) {
                                        "reload_login" -> {
                                            post {
                                                stopLoading()
                                                loadUrl("https://ninjasaga.cc/?minimal&air&noreauth=1")
                                            }
                                            return true
                                        }
                                    }
                                }
                                extractNinjaSagaEmulatorContext(raw)?.let { ctx ->
                                    lastEmulatorContext = ctx
                                    pendingPartialAuth?.let { partial ->
                                        authHandled = true
                                        stopLoading()
                                        onWebAuthCaptured(
                                            NinjaSagaWebAuthPayload(
                                                fbUid = partial.fbUid,
                                                fbName = partial.fbName,
                                                fbAt = partial.fbAt,
                                                fbSig = partial.fbSig,
                                                hashTime = ctx.hashTime,
                                                time = ctx.time,
                                            ),
                                        )
                                        return true
                                    }
                                }
                                extractNinjaSagaPartialAuth(raw)?.let { partial ->
                                    pendingPartialAuth = partial
                                    val ctx = lastEmulatorContext
                                    if (ctx != null && ctx.hashTime.isNotBlank()) {
                                        authHandled = true
                                        stopLoading()
                                        onWebAuthCaptured(
                                            NinjaSagaWebAuthPayload(
                                                fbUid = partial.fbUid,
                                                fbName = partial.fbName,
                                                fbAt = partial.fbAt,
                                                fbSig = partial.fbSig,
                                                hashTime = ctx.hashTime,
                                                time = ctx.time,
                                            ),
                                        )
                                    }
                                    return true
                                }
                                val payload = parseNinjaSagaWebAuth(raw, lastEmulatorContext)
                                return if (payload != null) {
                                    authHandled = true
                                    stopLoading()
                                    onWebAuthCaptured(payload)
                                    true
                                } else {
                                    false
                                }
                            }

                            override fun shouldOverrideUrlLoading(
                                view: WebView?,
                                request: WebResourceRequest?,
                            ): Boolean {
                                return tryHandle(request?.url?.toString())
                            }

                            override fun shouldOverrideUrlLoading(view: WebView?, url: String?): Boolean {
                                return tryHandle(url)
                            }

                            override fun onPageStarted(view: WebView?, url: String?, favicon: android.graphics.Bitmap?) {
                                super.onPageStarted(view, url, favicon)
                                tryHandle(url)
                            }

                            override fun onPageFinished(view: WebView?, url: String?) {
                                super.onPageFinished(view, url)
                                tryHandle(url)
                            }
                        }
                        loadUrl("https://ninjasaga.cc/?minimal&air")
                    }
                },
            )
        }
    }
}

private fun parseNinjaSagaWebAuth(rawUrl: String): NinjaSagaWebAuthPayload? {
    return parseNinjaSagaWebAuth(rawUrl, null)
}

private fun currentNinjaSagaCookieHeader(): String {
    return try {
        val manager = CookieManager.getInstance()
        manager.flush()
        manager.getCookie("https://ninjasaga.cc").orEmpty()
    } catch (_: Throwable) {
        ""
    }
}

private fun parseNinjaSagaWebAuth(
    rawUrl: String,
    emulatorContext: NinjaSagaEmulatorContext?,
): NinjaSagaWebAuthPayload? {
    if (rawUrl.isBlank()) return null
    if (rawUrl.startsWith("nsdata://")) {
        return null
    }

    return try {
        val uri = Uri.parse(rawUrl)
        val host = uri.host.orEmpty()
        val path = uri.path.orEmpty()
        if (!host.contains("ninjasaga.cc") || !path.contains("emulator.html")) {
            return null
        }
        val fbUid = uri.getQueryParameter("fb_uid").orEmpty()
        val fbName = URLDecoder.decode(uri.getQueryParameter("fb_name").orEmpty(), "UTF-8")
        val fbAt = uri.getQueryParameter("fb_at").orEmpty()
        val fbSig = uri.getQueryParameter("fb_sig").orEmpty()
        val hashTime = uri.getQueryParameter("hash_time").orEmpty()
        val time = uri.getQueryParameter("time")?.toIntOrNull() ?: 0
        if (fbUid.isBlank() || fbAt.isBlank() || fbSig.isBlank() || hashTime.isBlank()) {
            return null
        }
        NinjaSagaWebAuthPayload(
            fbUid = fbUid,
            fbName = fbName,
            fbAt = fbAt,
            fbSig = fbSig,
            hashTime = hashTime,
            time = time,
        )
    } catch (_: Throwable) {
        null
    }
}

private fun extractNinjaSagaPartialAuth(rawUrl: String): NinjaSagaPartialAuth? {
    if (!rawUrl.startsWith("nsdata://")) return null
    return try {
        val encoded = rawUrl.removePrefix("nsdata://")
        val decoded = String(Base64.decode(encoded, Base64.DEFAULT), Charsets.UTF_8)
        val parts = decoded.split("|||")
        if (parts.size < 4) return null
        NinjaSagaPartialAuth(
            fbUid = parts[0],
            fbName = parts[1],
            fbAt = parts[2],
            fbSig = parts[3],
        )
    } catch (_: Throwable) {
        null
    }
}

private fun extractNinjaSagaEmulatorContext(rawUrl: String): NinjaSagaEmulatorContext? {
    if (rawUrl.isBlank()) return null
    return try {
        val uri = Uri.parse(rawUrl)
        val host = uri.host.orEmpty()
        val path = uri.path.orEmpty()
        if (!host.contains("ninjasaga.cc") || !path.contains("emulator.html")) {
            return null
        }
        val hashTime = uri.getQueryParameter("hash_time").orEmpty()
        if (hashTime.isBlank()) {
            return null
        }
        NinjaSagaEmulatorContext(
            hashTime = hashTime,
            time = uri.getQueryParameter("time")?.toIntOrNull() ?: 0,
        )
    } catch (_: Throwable) {
        null
    }
}

private fun parseNinjaSagaNsDirective(rawUrl: String): NinjaSagaNsDirective? {
    val raw = rawUrl.trim()
    if (!raw.startsWith("nsdata://")) return null
    val payload = raw.removePrefix("nsdata://").trim().lowercase()
    return when (payload) {
        "session_expired", "notloggedin", "error" -> NinjaSagaNsDirective("reload_login")
        "close_webview" -> NinjaSagaNsDirective("close")
        else -> null
    }
}

@Composable
private fun BaseGameSelectionScreen(uiState: UiState, viewModel: AppViewModel) {
    val games = uiState.baseGames
    val currentGame = uiState.currentBaseGame

    ElevatedCard(colors = CardDefaults.elevatedCardColors(containerColor = Color(0xFF15110F))) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
            Text("Select Base Game", style = MaterialTheme.typography.headlineSmall, color = Color.White)
            Text(
                "Choose game type first, then continue to server selection.",
                color = Color(0xFFD8CFC3),
                style = MaterialTheme.typography.bodyMedium,
            )

            if (games.isEmpty()) {
                Text(
                    "Loading base game list...",
                    color = Color(0xFFC9D2D8),
                    style = MaterialTheme.typography.bodyMedium,
                )
            }

            games.forEach { game ->
                val isSelected = game.id == currentGame?.id
                Card(
                    colors = CardDefaults.cardColors(
                        containerColor = if (isSelected) Color(0xFF2B2317) else Color(0xFF202327),
                    ),
                    onClick = {
                        if (!isSelected) {
                            viewModel.selectBaseGame(game.id)
                        }
                    },
                ) {
                    Column(modifier = Modifier.fillMaxWidth().padding(16.dp)) {
                        Text(game.label, color = Color.White, style = MaterialTheme.typography.titleMedium)
                        if (game.serverSelectionNote.isNotBlank()) {
                            Text(
                                game.serverSelectionNote,
                                color = if (isSelected) Color(0xFFFFC978) else Color(0xFFC9D2D8),
                                style = MaterialTheme.typography.bodySmall,
                            )
                        }
                    }
                }
            }

            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                Checkbox(
                    checked = uiState.forceAmfSupportCurrentVersion,
                    onCheckedChange = viewModel::updateForceAmfSupportCurrentVersion,
                )
                Column(modifier = Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
                    Text(
                        "Skip version check",
                        color = Color.White,
                        style = MaterialTheme.typography.bodyMedium,
                    )
                    Text(
                        "When enabled, the app does not call check_version after selecting the game server and goes straight to login.",
                        color = Color(0xFFD8CFC3),
                        style = MaterialTheme.typography.bodySmall,
                    )
                }
            }

            Button(
                onClick = viewModel::continueFromBaseGameSelection,
                enabled = currentGame != null,
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text("Continue")
            }
        }
    }

}

@Composable
private fun AmfSelectionScreen(uiState: UiState, viewModel: AppViewModel) {
    val profiles = uiState.amfProfiles
    val currentProfile = uiState.currentAmfProfile
    val singleProfile = profiles.singleOrNull()

    ElevatedCard(colors = CardDefaults.elevatedCardColors(containerColor = Color(0xFF15110F))) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
            Text("Select Game Server", style = MaterialTheme.typography.headlineSmall, color = Color.White)
            Text(
                uiState.currentBaseGame?.serverSelectionNote?.ifBlank { "Choose the AMF server before login." }
                    ?: "Choose the AMF server before login.",
                color = Color(0xFFD8CFC3),
                style = MaterialTheme.typography.bodyMedium,
            )

            if (profiles.isEmpty()) {
                Text(
                    "Loading game server list... ",
                    color = Color(0xFFC9D2D8),
                    style = MaterialTheme.typography.bodyMedium,
                )
            }

            if (singleProfile != null) {
                Text(
                    "Only one server is available for ${uiState.currentBaseGame?.label ?: "this base game"}. Review it, then continue.",
                    color = Color(0xFFFFC978),
                    style = MaterialTheme.typography.bodyMedium,
                )
                Card(
                    colors = CardDefaults.cardColors(containerColor = Color(0xFF2B2317)),
                ) {
                    Column(modifier = Modifier.fillMaxWidth().padding(16.dp)) {
                        Text(singleProfile.label, color = Color.White, style = MaterialTheme.typography.titleMedium)
                        Text(
                            singleProfile.buildNum,
                            color = Color(0xFFFFC978),
                            style = MaterialTheme.typography.bodyMedium,
                        )
                    }
                }
                Button(
                    onClick = viewModel::continueFromServerSelection,
                    enabled = currentProfile != null,
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Text("Continue")
                }
            } else {
                profiles.forEach { profile ->
                    val isSelected = profile.id == currentProfile?.id
                    val isLocked = !uiState.billingSubscriptionActive && profile.id != "official"
                    Card(
                        colors = CardDefaults.cardColors(
                            containerColor = when {
                                isLocked -> Color(0xFF16191D)
                                isSelected -> Color(0xFF2B2317)
                                else -> Color(0xFF202327)
                            },
                        ),
                        onClick = {
                            if (!isSelected) {
                                viewModel.selectAmfProfile(profile.id)
                            }
                        },
                    ) {
                        Column(modifier = Modifier.fillMaxWidth().padding(16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween,
                                verticalAlignment = Alignment.CenterVertically,
                            ) {
                                Text(
                                    profile.label,
                                    color = if (isLocked) Color(0xFF8A9299) else Color.White,
                                    style = MaterialTheme.typography.titleMedium,
                                )
                                if (isLocked) {
                                    Text(
                                        "Locked",
                                        color = Color(0xFFFFC978),
                                        style = MaterialTheme.typography.labelMedium,
                                    )
                                }
                            }
                            Text(
                                profile.buildNum,
                                color = when {
                                    isLocked -> Color(0xFF6F7880)
                                    isSelected -> Color(0xFFFFC978)
                                    else -> Color(0xFFC9D2D8)
                                },
                                style = MaterialTheme.typography.bodyMedium,
                            )
                            if (isLocked) {
                                Text(
                                    "Subscription required",
                                    color = Color(0xFFB7C0C7),
                                    style = MaterialTheme.typography.bodySmall,
                                )
                            }
                        }
                    }
                }

                Button(
                    onClick = viewModel::continueFromServerSelection,
                    enabled = currentProfile != null,
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Text("Continue")
                }
            }
            OutlinedButton(
                onClick = viewModel::openBaseGameSelection,
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text("Back to Base Game")
            }
        }
    }

}

@Composable
private fun StartupSplashScreen(uiState: UiState) {
    val transition = rememberInfiniteTransition(label = "startup")
    val pulseScale by transition.animateFloat(
        initialValue = 0.92f,
        targetValue = 1.08f,
        animationSpec = infiniteRepeatable(
            animation = tween(durationMillis = 1800, easing = LinearEasing),
            repeatMode = RepeatMode.Reverse,
        ),
        label = "pulseScale",
    )
    val pulseAlpha by transition.animateFloat(
        initialValue = 0.35f,
        targetValue = 0.8f,
        animationSpec = infiniteRepeatable(
            animation = tween(durationMillis = 1800, easing = LinearEasing),
            repeatMode = RepeatMode.Reverse,
        ),
        label = "pulseAlpha",
    )

    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(
                Brush.verticalGradient(
                    colors = listOf(Color(0xFF050505), Color(0xFF241111), Color(0xFF090909)),
                ),
            )
            .padding(24.dp),
        contentAlignment = Alignment.Center,
    ) {
        Surface(
            modifier = Modifier
                .size(220.dp)
                .graphicsLayer {
                    scaleX = pulseScale
                    scaleY = pulseScale
                    alpha = pulseAlpha
                },
            shape = CircleShape,
            color = Color(0x22FFC978),
        ) {}

        Column(
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(18.dp),
        ) {
            Icon(
                painter = painterResource(R.mipmap.ic_launcher),
                contentDescription = null,
                modifier = Modifier.size(92.dp),
                tint = Color.Unspecified,
            )
            Text("NSe Panel", style = MaterialTheme.typography.headlineMedium, color = Color.White)
            Text("Panel Version ${uiState.buildNumber}", color = Color(0xFFFFC978))
            uiState.currentAmfProfile?.let {
                Text(it.label, color = Color(0xFFD8CFC3), style = MaterialTheme.typography.titleSmall)
            }
            if (!uiState.versionChecked) {
                CircularProgressIndicator(
                    color = Color(0xFFE1A44A),
                    trackColor = Color(0x33222222),
                )
            } else if (!uiState.startupReady) {
                Text(
                    uiState.startupFailureTitle,
                    color = Color(0xFFFFCC80),
                    style = MaterialTheme.typography.titleMedium,
                )
            }
            Text(
                text = if (uiState.versionChecked) {
                    uiState.versionMessage
                } else {
                    "Checking panel status..."
                },
                color = Color(0xFFD8CFC3),
                style = MaterialTheme.typography.bodyMedium,
            )
            uiState.statusMessage?.let {
                Text(it, color = Color(0xFFF5B971), style = MaterialTheme.typography.bodyMedium)
            }
        }
    }
}

@Composable
private fun CharacterChooser(uiState: UiState, viewModel: AppViewModel) {
    ElevatedCard(colors = CardDefaults.elevatedCardColors(containerColor = Color(0xFF12171A))) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Text("Choose Character", style = MaterialTheme.typography.headlineSmall, color = Color.White)
            uiState.characters.forEach { character ->
                Card(
                    colors = CardDefaults.cardColors(containerColor = Color(0xFF202B31)),
                    onClick = { viewModel.selectCharacter(character.index) },
                ) {
                    Column(modifier = Modifier.fillMaxWidth().padding(16.dp)) {
                        Text(character.name, color = Color.White, style = MaterialTheme.typography.titleMedium)
                        Text("Level ${character.level}", color = Color(0xFFC7D6DF))
                        Text("ID ${character.id}", color = Color(0xFF8FA5B3))
                    }
                }
            }
            OutlinedButton(
                onClick = viewModel::logout,
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text("Logout")
            }
        }
    }
}

@Composable
private fun DashboardScreen(
    uiState: UiState,
    viewModel: AppViewModel,
    onAddTimeClick: () -> Unit,
    rewardedButtonLabel: String,
    rewardedButtonEnabled: Boolean,
) {
    Box(modifier = Modifier.fillMaxSize()) {
        LazyColumn(
            modifier = Modifier.fillMaxSize(),
            contentPadding = PaddingValues(16.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            item {
                CharacterCard(uiState, viewModel)
            }
            item {
                ActionPanel(uiState, viewModel)
            }
            item {
                LogPanel(uiState, viewModel)
            }
        }

        if (!uiState.hasBillingAccess) {
            BillingExpiredOverlay(
                runningAction = uiState.runningAction,
                onAddTimeClick = onAddTimeClick,
                rewardedButtonLabel = rewardedButtonLabel,
                rewardedButtonEnabled = rewardedButtonEnabled,
                showAds = !uiState.billingDisableAds,
            )
        }
    }
}

@Composable
private fun CharacterCard(uiState: UiState, viewModel: AppViewModel) {
    val character = uiState.character ?: return
    ElevatedCard(colors = CardDefaults.elevatedCardColors(containerColor = Color(0xFF151515))) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text(character.name, style = MaterialTheme.typography.headlineSmall, color = Color.White)
            Text("Level ${character.level} | XP ${character.xp}", color = Color(0xFFE5D4BE))
            Text("Gold ${character.gold} | Tokens ${character.tokens}", color = Color(0xFFC6DE94))
            uiState.runningAction?.let { Text("Running: $it", color = Color(0xFFF0A85B)) }
            uiState.statusMessage?.let { Text(it, color = Color(0xFFE0D0B8)) }
            Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                Button(onClick = viewModel::refreshCharacter, modifier = Modifier.weight(1f)) {
                    Text("Refresh")
                }
                OutlinedButton(onClick = viewModel::changeCharacter, modifier = Modifier.weight(1f)) {
                    Text("Change Character")
                }
            }
            Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                OutlinedButton(onClick = viewModel::logout, modifier = Modifier.weight(1f)) {
                    Text("Logout")
                }
                Spacer(modifier = Modifier.weight(1f))
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun ActionPanel(uiState: UiState, viewModel: AppViewModel) {
    var selectedCategory by rememberSaveable { mutableStateOf<String?>(null) }
    var showNinjaSagaSettings by rememberSaveable { mutableStateOf(false) }
    var showSageSettings by rememberSaveable { mutableStateOf(false) }
    var showRiftSettings by rememberSaveable { mutableStateOf(false) }
    val isNinjaSaga = uiState.currentBaseGame?.id == "ninjasaga"
    val isZenshin = uiState.currentBaseGame?.id == "zenshin"
    val isNinjaSagaFamily = isNinjaSaga || isZenshin
    val isSage = uiState.currentBaseGame?.id == "sage"
    val isRift = uiState.currentBaseGame?.id == "rift"
    val categorizedActions = remember(uiState.actions) {
        if (isNinjaSaga) {
            mapOf(
                "main" to listOf("leveling", "tp_training", "ss_training", "eudemon_garden"),
                "events" to listOf("motherday_event", "sakura_event"),
                "war" to emptyList(),
            )
        } else if (isZenshin) {
            mapOf(
                "main" to listOf("leveling", "tp_training", "ss_training", "eudemon_garden"),
                "events" to emptyList(),
                "war" to emptyList(),
            )
        } else if (isRift) {
            mapOf(
                "main" to listOf("finisher_action", "leveling", "daily_missions", "eudemon_garden", "hunting_house"),
                "events" to listOf("easter_event"),
                "war" to emptyList(),
            )
        } else {
            mapOf(
                "main" to listOf("leveling", "daily", "eudemon", "monster_hunt", "mission_s"),
                "events" to listOf("aniv_event", "aniv_special", "sakura_event", "easter_event", "worldcup_event", "minigame_event"),
                "war" to listOf("shadow_war", "clan_war"),
            )
        }
    }
    val visibleActions = if (selectedCategory == null) {
        emptyList()
    } else {
        val allowedKeys = categorizedActions[selectedCategory].orEmpty().toSet()
        uiState.actions.filter { it.key in allowedKeys }
    }
    val categoryButtons = listOf(
        "main" to "Main Action",
        "events" to "Events",
        "war" to "War",
    ).filter { (key, _) ->
        val allowedKeys = categorizedActions[key].orEmpty().toSet()
        uiState.actions.any { it.key in allowedKeys }
    }
    LaunchedEffect(selectedCategory, categoryButtons) {
        if (selectedCategory != null && categoryButtons.none { it.first == selectedCategory }) {
            selectedCategory = null
        }
    }

    ElevatedCard(colors = CardDefaults.elevatedCardColors(containerColor = Color(0xFF101314))) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
            Text("Automation Actions", style = MaterialTheme.typography.headlineSmall, color = Color.White)
            if (isNinjaSagaFamily) {
                OutlinedButton(
                    onClick = {
                        viewModel.loadNinjaSagaSettings()
                        showNinjaSagaSettings = true
                    },
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Text(if (isZenshin) "Ninja Zenshin Settings" else "NinjaSaga Settings")
                }
            } else if (isSage) {
                OutlinedButton(
                    onClick = {
                        viewModel.loadSageSettings()
                        showSageSettings = true
                    },
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Text("Ninja Sage Settings")
                }
            } else if (isRift) {
                OutlinedButton(
                    onClick = {
                        viewModel.loadRiftSettings()
                        showRiftSettings = true
                    },
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Text("Ninja Rift Settings")
                }
            }
            if (!uiState.hasBillingAccess) {
                Text(
                    "Actions are locked until you add billing time. Watch a rewarded ad with +Time to get +2 hours.",
                    color = Color(0xFFFFCC80),
                )
            }
            if (uiState.running) {
                Button(
                    onClick = viewModel::stopAction,
                    colors = ButtonDefaults.buttonColors(containerColor = Color(0xFFC44B3C)),
                ) {
                    Text("Stop Current Action")
                }
            } else if (uiState.actionStateSyncing) {
                Text(
                    "Refreshing current action state...",
                    color = Color(0xFFFFCC80),
                    style = MaterialTheme.typography.bodyMedium,
                )
            }

            if (selectedCategory == null) {
                categoryButtons.chunked(2).forEach { buttonRow ->
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(12.dp),
                    ) {
                        buttonRow.forEach { (key, title) ->
                            CategoryButtonCard(
                                title = title,
                                onClick = { selectedCategory = key },
                                modifier = Modifier.weight(1f),
                            )
                        }
                        if (buttonRow.size == 1) {
                            Spacer(modifier = Modifier.weight(1f))
                        }
                    }
                }
            } else {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Text(
                        text = when (selectedCategory) {
                            "main" -> "Main Action"
                            "events" -> "Events"
                            "war" -> "War"
                            else -> "Actions"
                        },
                        color = Color(0xFFFFC978),
                        style = MaterialTheme.typography.titleMedium,
                    )
                    TextButton(onClick = { selectedCategory = null }) {
                        Text("Back")
                    }
                }
                visibleActions.chunked(2).forEach { actionRow ->
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(12.dp),
                    ) {
                        actionRow.forEach { action ->
                            ActionButtonCard(
                                action = action,
                                uiState = uiState,
                                viewModel = viewModel,
                                modifier = Modifier.weight(1f),
                            )
                        }
                        if (actionRow.size == 1) {
                            Spacer(modifier = Modifier.weight(1f))
                        }
                    }
                }
            }
        }
    }
    if (showNinjaSagaSettings && isNinjaSagaFamily) {
        NinjaSagaSettingsDialog(
            title = if (isZenshin) "Ninja Zenshin Settings" else "NinjaSaga Settings",
            current = uiState.ninjaSagaSettings,
            onDismiss = { showNinjaSagaSettings = false },
            onSave = { settings ->
                viewModel.saveNinjaSagaSettings(settings)
                showNinjaSagaSettings = false
            },
        )
    }
    if (showSageSettings && isSage) {
        SageSettingsDialog(
            current = uiState.sageSettings,
            onDismiss = { showSageSettings = false },
            onSave = { settings ->
                viewModel.saveSageSettings(settings)
                showSageSettings = false
            },
        )
    }
    if (showRiftSettings && isRift) {
        RiftSettingsDialog(
            current = uiState.riftSettings,
            skillOptions = uiState.riftSkillOptions,
            onDismiss = { showRiftSettings = false },
            onSave = { settings ->
                viewModel.saveRiftSettings(settings)
                showRiftSettings = false
            },
        )
    }
}

@Composable
private fun NinjaSagaClanWarCaptchaOverlay(
    uiState: UiState,
    viewModel: AppViewModel,
) {
    val captchaJson = uiState.clanWarCaptcha.challengeJson

    LaunchedEffect(uiState.clanWarCaptcha.required, captchaJson, uiState.clanWarCaptcha.loading, uiState.clanWarCaptcha.verifying) {
        if (uiState.clanWarCaptcha.required && captchaJson.isNullOrBlank() && !uiState.clanWarCaptcha.loading && !uiState.clanWarCaptcha.verifying) {
            viewModel.loadClanWarCaptchaChallenge(currentNinjaSagaCookieHeader())
        }
    }

    Dialog(
        onDismissRequest = {},
        properties = DialogProperties(
            dismissOnBackPress = false,
            dismissOnClickOutside = false,
            usePlatformDefaultWidth = false,
        ),
    ) {
        Card(
            modifier = Modifier
                .fillMaxSize()
                .padding(12.dp),
            colors = CardDefaults.cardColors(containerColor = Color(0xFF0D0D0D)),
        ) {
            Column(
                modifier = Modifier.fillMaxSize(),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 12.dp, vertical = 10.dp),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Column(modifier = Modifier.weight(1f)) {
                        Text("NinjaSaga Clan War Captcha", color = Color.White, style = MaterialTheme.typography.titleMedium)
                        Text(
                            uiState.clanWarCaptcha.message.takeIf { it.isNotBlank() && it != "null" }
                                ?: "Solve the captcha to continue Clan War.",
                            color = Color(0xFFE0D0B8),
                            style = MaterialTheme.typography.bodySmall,
                        )
                    }
                    OutlinedButton(onClick = viewModel::stopAction) {
                        Text("Stop")
                    }
                }
                if (uiState.clanWarCaptcha.loading) {
                    Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                        CircularProgressIndicator()
                    }
                } else {
                    Box(
                        modifier = Modifier
                            .fillMaxWidth()
                            .weight(1f, fill = true)
                            .padding(horizontal = 12.dp),
                    ) {
                        NinjaSagaCaptchaChallengeWebView(
                            challengeJson = captchaJson,
                            verifying = uiState.clanWarCaptcha.verifying,
                            onGenerateResult = { resultJson ->
                                viewModel.handleClanWarCaptchaGenerateResult(resultJson)
                            },
                            onVerifyResult = { resultJson ->
                                viewModel.submitClanWarCaptchaWebResult(resultJson, currentNinjaSagaCookieHeader())
                            },
                        )
                    }
                }
                uiState.clanWarCaptcha.submittedAnswer?.takeIf { it.isNotBlank() }?.let { submittedAnswer ->
                    ElevatedCard(
                        colors = CardDefaults.elevatedCardColors(containerColor = Color(0xFF151515)),
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(horizontal = 12.dp),
                    ) {
                        Column(
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(10.dp),
                            verticalArrangement = Arrangement.spacedBy(4.dp),
                        ) {
                            Text("Verify Answer", color = Color(0xFFFFC978), style = MaterialTheme.typography.titleSmall)
                            Text(submittedAnswer, color = Color(0xFFE0D0B8), style = MaterialTheme.typography.bodySmall)
                        }
                    }
                }
                uiState.clanWarCaptcha.debugJson
                    ?.takeIf { it.isNotBlank() && uiState.clanWarCaptcha.submittedAnswer?.isNotBlank() == true }
                    ?.let { debugJson ->
                    ElevatedCard(
                        colors = CardDefaults.elevatedCardColors(containerColor = Color(0xFF141A1F)),
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(horizontal = 12.dp),
                    ) {
                        Column(
                            modifier = Modifier
                                .fillMaxWidth()
                                .heightIn(max = 180.dp)
                                .verticalScroll(rememberScrollState())
                                .padding(10.dp),
                            verticalArrangement = Arrangement.spacedBy(6.dp),
                        ) {
                            Text("Captcha Debug", color = Color(0xFFFFC978), style = MaterialTheme.typography.titleSmall)
                            Text(
                                text = debugJson,
                                color = Color(0xFFE0D0B8),
                                style = MaterialTheme.typography.bodySmall,
                            )
                        }
                    }
                }
                uiState.clanWarCaptcha.error?.takeIf { it.isNotBlank() }?.let { errorText ->
                    Column(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(horizontal = 12.dp, vertical = 8.dp),
                        verticalArrangement = Arrangement.spacedBy(8.dp),
                    ) {
                        Text(
                            text = errorText,
                            color = Color(0xFFFF8A80),
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun NinjaSagaCaptchaChallengeWebView(
    challengeJson: String?,
    verifying: Boolean,
    onGenerateResult: (String) -> Unit,
    onVerifyResult: (String) -> Unit,
) {
    val challengeRef = remember { arrayOf<String?>(null) }
    AndroidView(
        modifier = Modifier.fillMaxSize(),
        factory = { ctx ->
            WebView(ctx).apply {
                CookieManager.getInstance().setAcceptCookie(true)
                CookieManager.getInstance().setAcceptThirdPartyCookies(this, true)
                settings.javaScriptEnabled = true
                settings.domStorageEnabled = true
                settings.loadsImagesAutomatically = true
                webChromeClient = WebChromeClient()
                webViewClient = object : WebViewClient() {}
                addJavascriptInterface(
                    object {
                        @JavascriptInterface
                        fun onGenerateResult(resultJson: String) {
                            post {
                                onGenerateResult(resultJson)
                            }
                        }

                        @JavascriptInterface
                        fun onVerifyResult(resultJson: String) {
                            post {
                                onVerifyResult(resultJson)
                            }
                        }

                        @JavascriptInterface
                        fun log(message: String) {
                        }
                    },
                    "AndroidCaptcha",
                )
                setBackgroundColor(android.graphics.Color.TRANSPARENT)
                setOnLongClickListener { true }
                isLongClickable = false
                setHapticFeedbackEnabled(false)
            }
        },
        update = { webView ->
            if (challengeRef[0] != challengeJson) {
                challengeRef[0] = challengeJson
                if (challengeJson.isNullOrBlank()) {
                    webView.loadDataWithBaseURL(
                        null,
                        "<html><body style=\"background:#0d0d0d;color:#fff;font-family:sans-serif;text-align:center;padding-top:24px;\">Waiting for captcha challenge...</body></html>",
                        "text/html",
                        "utf-8",
                        null,
                    )
                } else {
                    val cookieHeader = currentNinjaSagaCookieHeader()
                    if (cookieHeader.isNotBlank()) {
                        val cookieManager = CookieManager.getInstance()
                        cookieHeader.split(";").map { it.trim() }.filter { it.isNotBlank() }.forEach { cookie ->
                            try {
                                cookieManager.setCookie("https://ninjasaga.cc/", cookie)
                            } catch (_: Throwable) {
                            }
                        }
                        cookieManager.flush()
                    }
                    webView.loadDataWithBaseURL(
                        "https://ninjasaga.cc/",
                        buildNinjaSagaCaptchaHtml(challengeJson),
                        "text/html",
                        "utf-8",
                        null,
                    )
                }
            } else if (!challengeJson.isNullOrBlank()) {
                webView.evaluateJavascript(
                    "window.__setVerifyState && window.__setVerifyState(${if (verifying) "true" else "false"});",
                    null,
                )
            }
        },
    )
}

private fun buildNinjaSagaCaptchaHtml(challengeJson: String): String {
    val encodedChallenge = Base64.encodeToString(challengeJson.toByteArray(Charsets.UTF_8), Base64.NO_WRAP)
    return """
        <!DOCTYPE html>
        <html>
        <head>
            <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no" />
            <style>
                html,body { margin:0; padding:0; background:#0d0d0d; color:#f5e7d0; font-family:sans-serif; min-height:100%; }
                .wrap { max-width:420px; margin:0 auto; padding:8px 10px 16px; text-align:center; user-select:none; -webkit-user-select:none; }
                .prompt { margin-bottom:10px; }
                .prompt img { max-width:100%; height:auto; display:block; margin:0 auto; }
                .grid { display:grid; grid-template-columns:repeat(3, 1fr); gap:6px; margin-bottom:12px; }
                .tile { position:relative; border:3px solid transparent; border-radius:6px; overflow:hidden; }
                .tile img { width:100%; display:block; }
                .tile.selected { border-color:#ff6600; }
                .tile .check { position:absolute; top:4px; right:4px; width:18px; height:18px; display:none; align-items:center; justify-content:center; border-radius:50%; background:#cc0000; color:#fff; font-size:12px; font-weight:bold; }
                .tile.selected .check { display:flex; }
                .frame { position:relative; width:100%; margin:0 auto 10px; border:2px solid #8b2200; border-radius:8px; overflow:hidden; line-height:0; box-sizing:border-box; }
                .frame > img.bg { width:100%; display:block; }
                .slider-piece, .drag-piece, .rotate-piece { position:absolute; z-index:2; user-select:none; -webkit-user-drag:none; }
                .slider-piece, .rotate-piece { pointer-events:none; }
                .drag-piece { pointer-events:auto; cursor:grab; touch-action:none; }
                .rotate-piece { top:0; left:0; width:100%; height:100%; object-fit:contain; transform-origin:center center; }
                .slider-track { position:relative; width:100%; height:38px; margin:0 auto 10px; border:2px solid #8b2200; border-radius:20px; background:linear-gradient(180deg,#c8a96e,#b89858); box-sizing:border-box; }
                .slider-thumb { position:absolute; top:2px; width:32px; height:30px; border-radius:18px; background:linear-gradient(180deg,#ff7a00,#c65300); border:2px solid #8b2200; box-sizing:border-box; }
                .slider-label { position:absolute; left:36px; right:6px; top:0; height:34px; line-height:34px; color:rgba(0,0,0,.55); font-weight:700; font-size:14px; pointer-events:none; }
                .rotate-row { display:flex; align-items:center; justify-content:center; gap:12px; margin-bottom:12px; }
                .rotate-btn { width:42px; height:42px; background:none; border:none; padding:0; }
                .rotate-btn img { width:100%; height:100%; display:block; }
                .actions { display:flex; justify-content:center; margin-top:12px; }
                .verify-btn { height:42px; border:none; background:none; padding:0; }
                .verify-btn img { height:42px; display:block; }
                .verify-btn.pressed { transform:translateY(1px) scale(.98); filter:brightness(.92); }
                .verify-btn.disabled { opacity:.45; pointer-events:none; }
                .render-error { color:#ff9a9a; background:#1d1010; border:1px solid #7b2d2d; border-radius:8px; padding:12px; white-space:pre-wrap; text-align:left; }
            </style>
        </head>
        <body>
            <div id="app" class="wrap"></div>
            <script>
                const GENERATE_ENDPOINT = "https://ninjasaga.cc/api.php/custom-captcha/generate";
                const VERIFY_ENDPOINT = "https://ninjasaga.cc/api.php/verify-captcha";
                let challenge = null;
                let webContext = {};
                let selected = [];
                let sliderAnswer = 0;
                let dragAnswer = { x: 0, y: 0 };
                let rotateAnswer = 0;
                let interacted = false;
                let verifyLocked = false;
                let mt = [];
                function seedBrowserStorage() {
                    try {
                        const ctx = webContext || {};
                        const userSessionKey = String(ctx.user_session_key || "L9i3H4Q4ye");
                        const uuid = String(ctx.uuid || "");
                        const workingCDN = String(ctx.working_cdn || "https://cdn.ninjasaga.cc/");
                        const showBadge = String(ctx.show_emulator_badge === true ? "true" : "false");
                        const webAuth = ctx.web_auth && typeof ctx.web_auth === "object" ? ctx.web_auth : null;
                        if (uuid) {
                            localStorage.setItem("uuid", uuid);
                            sessionStorage.setItem("uuid", uuid);
                        }
                        localStorage.setItem("showEmulatorBadge", showBadge);
                        localStorage.setItem("workingCDN", workingCDN);
                        sessionStorage.setItem("workingCDN", workingCDN);
                        if (webAuth && (webAuth.token || webAuth.signature || webAuth.player_id)) {
                            const sessionBlob = JSON.stringify(webAuth);
                            localStorage.setItem(userSessionKey, sessionBlob);
                            sessionStorage.setItem(userSessionKey, sessionBlob);
                        }
                    } catch (error) {
                    }
                }
                function getApiHeaders() {
                    const headers = {
                        "Content-Type": "application/json",
                        "Accept": "application/json, text/plain, */*",
                        "X-Requested-With": "XMLHttpRequest"
                    };
                    try {
                        const userSessionKey = String((webContext || {}).user_session_key || "L9i3H4Q4ye");
                        const raw = localStorage.getItem(userSessionKey) || sessionStorage.getItem(userSessionKey) || "";
                        if (raw) {
                            const sessionData = JSON.parse(raw);
                            if (sessionData && sessionData.token) {
                                headers["Authorization"] = "Bearer " + sessionData.token;
                            }
                        }
                    } catch (error) {
                    }
                    return headers;
                }
                async function parseFetchResponse(resp) {
                    const text = await resp.text();
                    let body = null;
                    try {
                        body = text ? JSON.parse(text) : {};
                    } catch (error) {
                        body = { success: false, message: text || ("HTTP " + resp.status) };
                    }
                    return { status: resp.status, body: body };
                }
                async function generateChallenge() {
                    const payload = {
                        uuid: String((webContext || {}).uuid || localStorage.getItem("uuid") || "")
                    };
                    const requestMeta = {
                        endpoint: "api.php/custom-captcha/generate",
                        payload: payload
                    };
                    try {
                        const resp = await fetch(GENERATE_ENDPOINT, {
                            method: "POST",
                            credentials: "include",
                            headers: getApiHeaders(),
                            body: JSON.stringify(payload)
                        });
                        const parsed = await parseFetchResponse(resp);
                        const responseBody = parsed.body && typeof parsed.body === "object" ? parsed.body : {};
                        const result = {
                            success: !!responseBody.success && !!responseBody.challenge,
                            message: String(responseBody.message || ""),
                            challenge: responseBody.challenge || null,
                            debug: {
                                generate_request: requestMeta,
                                generate_response: {
                                    status: parsed.status,
                                    body: responseBody
                                }
                            }
                        };
                        if (result.success) {
                            challenge = responseBody.challenge;
                            selected = [];
                            sliderAnswer = Number(challenge.start_x || 0);
                            dragAnswer = { x: Number(challenge.start_x || 0), y: Number(challenge.start_y || 0) };
                            rotateAnswer = Number(challenge.start_angle || 0);
                            interacted = false;
                            mt = [];
                            render();
                        } else {
                            showRenderError(result.message || "Failed to load captcha challenge");
                        }
                        AndroidCaptcha.onGenerateResult(JSON.stringify(result));
                    } catch (error) {
                        showRenderError("Captcha generate failed: " + (error && error.message ? error.message : String(error)));
                        AndroidCaptcha.onGenerateResult(JSON.stringify({
                            success: false,
                            message: error && error.message ? error.message : String(error),
                            challenge: null,
                            debug: {
                                generate_request: requestMeta,
                                generate_response: {
                                    status: 0,
                                    body: {
                                        success: false,
                                        message: error && error.message ? error.message : String(error)
                                    }
                                }
                            }
                        }));
                    }
                }
                function showRenderError(message) {
                    const app = document.getElementById("app");
                    app.innerHTML = '<div class="render-error">' + String(message || 'Captcha render failed') + '</div>';
                }
                function record(x, y) {
                    const rx = Math.round(Number(x || 0));
                    const ry = Math.round(Number(y || 0));
                    mt.push(rx + "," + ry + "," + (Date.now() % 100000));
                    if (mt.length > 180) mt = mt.slice(mt.length - 180);
                }
                document.addEventListener("mousemove", (e) => record(e.clientX, e.clientY), { passive:true });
                document.addEventListener("mousedown", (e) => record(e.clientX, e.clientY), { passive:true });
                document.addEventListener("mouseup", (e) => record(e.clientX, e.clientY), { passive:true });
                document.addEventListener("touchstart", (e) => {
                    const t = e.touches && e.touches[0];
                    if (t) record(t.clientX, t.clientY);
                }, { passive:true });
                document.addEventListener("touchmove", (e) => {
                    const t = e.touches && e.touches[0];
                    if (t) record(t.clientX, t.clientY);
                }, { passive:true });
                document.addEventListener("touchend", (e) => {
                    const t = e.changedTouches && e.changedTouches[0];
                    if (t) record(t.clientX, t.clientY);
                }, { passive:true });
                function clamp(v, min, max) { return Math.max(min, Math.min(max, v)); }
                function render() {
                    const app = document.getElementById("app");
                    if (!challenge || typeof challenge !== "object") {
                        showRenderError("Captcha challenge is empty.");
                        return;
                    }
                    let html = '<div class="prompt"><img src="' + challenge.prompt + '" draggable="false" /></div>';
                    if (challenge.type === "grid_color") {
                        html += '<div class="grid">';
                        (challenge.tiles || []).forEach((tile, idx) => {
                            html += '<div class="tile" data-idx="' + idx + '"><img src="' + tile + '" draggable="false" /><div class="check">&#10003;</div></div>';
                        });
                        html += '</div>';
                    } else if (challenge.type === "slider") {
                        html += '<div class="frame" id="sliderFrame"><img class="bg" id="sliderBg" src="' + challenge.background + '" draggable="false" /><img class="slider-piece" id="sliderPiece" src="' + challenge.piece + '" draggable="false" /></div>';
                        html += '<div class="slider-track" id="sliderTrack"><div class="slider-thumb" id="sliderThumb"></div><div class="slider-label">Slide to fit</div></div>';
                    } else if (challenge.type === "drag_shape") {
                        html += '<div class="frame" id="dragFrame"><img class="bg" id="dragBg" src="' + challenge.background + '" draggable="false" /><img class="drag-piece" id="dragPiece" src="' + challenge.piece + '" draggable="false" /></div>';
                    } else if (challenge.type === "rotate") {
                        html += '<div class="rotate-row"><button class="rotate-btn" id="rotateLeft"><img src="' + challenge.arrow_left + '" draggable="false" /></button><div class="frame" style="width:180px" id="rotateFrame"><img class="bg" src="' + challenge.background + '" draggable="false" /><img class="rotate-piece" id="rotatePiece" src="' + challenge.piece + '" draggable="false" /></div><button class="rotate-btn" id="rotateRight"><img src="' + challenge.arrow_right + '" draggable="false" /></button></div>';
                    } else {
                        html += '<div>Unsupported captcha type: ' + challenge.type + '</div>';
                    }
                    html += '<div class="actions"><button class="verify-btn" id="verifyBtn"><img src="' + challenge.btn_img + '" draggable="false" /></button></div>';
                    app.innerHTML = html;
                    bind();
                }
                function setVerifyVisualState() {
                    const btn = document.getElementById("verifyBtn");
                    if (!btn) return;
                    btn.classList.toggle("disabled", !!verifyLocked);
                }
                window.__setVerifyState = function(flag) {
                    verifyLocked = !!flag;
                    setVerifyVisualState();
                };
                async function submitAnswer(answer) {
                    if (verifyLocked) return;
                    verifyLocked = true;
                    setVerifyVisualState();
                    const payload = {
                        challenge_id: String(challenge.challenge_id || ""),
                        answer: String(answer || ""),
                        hmac: String(challenge.hmac || ""),
                        mt: mt,
                        uuid: String((webContext || {}).uuid || localStorage.getItem("uuid") || "")
                    };
                    const requestMeta = {
                        endpoint: "api.php/verify-captcha",
                        payload: payload
                    };
                    try {
                        const resp = await fetch(VERIFY_ENDPOINT, {
                            method: "POST",
                            credentials: "include",
                            headers: getApiHeaders(),
                            body: JSON.stringify(payload)
                        });
                        const parsed = await parseFetchResponse(resp);
                        const responseBody = parsed.body && typeof parsed.body === "object" ? parsed.body : {};
                        AndroidCaptcha.onVerifyResult(JSON.stringify({
                            success: !!responseBody.success,
                            message: String(responseBody.message || ""),
                            answer: payload.answer,
                            debug: {
                                verify_request: requestMeta,
                                verify_response: {
                                    status: parsed.status,
                                    body: responseBody
                                }
                            }
                        }));
                    } catch (error) {
                        AndroidCaptcha.onVerifyResult(JSON.stringify({
                            success: false,
                            message: error && error.message ? error.message : String(error),
                            answer: payload.answer,
                            debug: {
                                verify_request: requestMeta,
                                verify_response: {
                                    status: 0,
                                    body: {
                                        success: false,
                                        message: error && error.message ? error.message : String(error)
                                    }
                                }
                            }
                        }));
                    }
                }
                function bind() {
                    const verifyBtn = document.getElementById("verifyBtn");
                    if (verifyBtn) {
                        verifyBtn.addEventListener("pointerdown", () => verifyBtn.classList.add("pressed"));
                        verifyBtn.addEventListener("pointerup", () => verifyBtn.classList.remove("pressed"));
                        verifyBtn.addEventListener("pointercancel", () => verifyBtn.classList.remove("pressed"));
                        verifyBtn.addEventListener("click", () => {
                            if (challenge.type === "grid_color") {
                                if (!selected.length) return;
                                submitAnswer(selected.slice().sort((a,b) => a-b).join(","));
                            } else if (challenge.type === "slider") {
                                if (!interacted) return;
                                submitAnswer(String(Math.round(sliderAnswer)));
                            } else if (challenge.type === "drag_shape") {
                                if (!interacted) return;
                                submitAnswer(Math.round(dragAnswer.x) + "," + Math.round(dragAnswer.y));
                            } else if (challenge.type === "rotate") {
                                if (!interacted) return;
                                submitAnswer(String(Math.round(rotateAnswer)));
                            }
                        });
                    }
                    if (challenge.type === "grid_color") {
                        document.querySelectorAll(".tile").forEach((tile) => {
                            tile.addEventListener("click", () => {
                                interacted = true;
                                const idx = Number(tile.getAttribute("data-idx"));
                                const pos = selected.indexOf(idx);
                                if (pos >= 0) {
                                    selected.splice(pos, 1);
                                    tile.classList.remove("selected");
                                } else {
                                    selected.push(idx);
                                    tile.classList.add("selected");
                                }
                            });
                        });
                    } else if (challenge.type === "slider") {
                        const bg = document.getElementById("sliderBg");
                        const piece = document.getElementById("sliderPiece");
                        const track = document.getElementById("sliderTrack");
                        const thumb = document.getElementById("sliderThumb");
                        const sourceW = Number(challenge.track_w || 380);
                        const maxAnswer = Number(challenge.max_x || 0);
                        let dragging = false;
                        function renderPositions() {
                            if (!bg || !piece || !track || !thumb) return;
                            const bgWidth = bg.clientWidth || sourceW;
                            const scale = bgWidth / sourceW;
                            piece.style.top = "0px";
                            piece.style.left = (sliderAnswer * scale) + "px";
                            if (bg.naturalWidth > 0 && bg.naturalHeight > 0) {
                                piece.style.height = bg.clientHeight + "px";
                            }
                            const trackRange = Math.max(1, track.clientWidth - thumb.clientWidth - 4);
                            const thumbX = maxAnswer > 0 ? (sliderAnswer / maxAnswer) * trackRange : 0;
                            thumb.style.left = (2 + thumbX) + "px";
                        }
                        function updateFromClient(clientX) {
                            if (!bg || !track || !thumb) return;
                            const rect = track.getBoundingClientRect();
                            const trackRange = Math.max(1, rect.width - thumb.clientWidth - 4);
                            let x = clamp(clientX - rect.left - thumb.clientWidth / 2, 0, trackRange);
                            sliderAnswer = maxAnswer > 0 ? (x / trackRange) * maxAnswer : 0;
                            interacted = true;
                            renderPositions();
                        }
                        const start = (clientX) => { dragging = true; updateFromClient(clientX); };
                        const move = (clientX) => { if (dragging) updateFromClient(clientX); };
                        const end = () => { dragging = false; };
                        thumb.addEventListener("mousedown", (e) => { e.preventDefault(); start(e.clientX); });
                        thumb.addEventListener("touchstart", (e) => { const t = e.touches[0]; if (!t) return; e.preventDefault(); start(t.clientX); }, { passive:false });
                        document.addEventListener("mousemove", (e) => move(e.clientX));
                        document.addEventListener("touchmove", (e) => { const t = e.touches[0]; if (!t) return; move(t.clientX); }, { passive:true });
                        document.addEventListener("mouseup", end);
                        document.addEventListener("touchend", end, { passive:true });
                        bg.addEventListener("load", renderPositions);
                        window.addEventListener("resize", renderPositions);
                        renderPositions();
                    } else if (challenge.type === "drag_shape") {
                        const bg = document.getElementById("dragBg");
                        const piece = document.getElementById("dragPiece");
                        const frame = document.getElementById("dragFrame");
                        const sourceW = Number(challenge.width || 380);
                        const sourceH = Number(challenge.height || 220);
                        const pieceW = Number(challenge.piece_w || 0);
                        const pieceH = Number(challenge.piece_h || 0);
                        let dragging = false;
                        let offsetX = 0;
                        let offsetY = 0;
                        function renderPositions() {
                            if (!bg || !piece) return;
                            const scaleX = (bg.clientWidth || sourceW) / sourceW;
                            const scaleY = (bg.clientHeight || sourceH) / sourceH;
                            piece.style.left = (dragAnswer.x * scaleX) + "px";
                            piece.style.top = (dragAnswer.y * scaleY) + "px";
                            if (pieceW > 0) piece.style.width = (pieceW * scaleX) + "px";
                            if (pieceH > 0) piece.style.height = (pieceH * scaleY) + "px";
                        }
                        function updateFromClient(clientX, clientY) {
                            if (!bg || !piece || !frame) return;
                            const rect = bg.getBoundingClientRect();
                            const scaleX = (bg.clientWidth || sourceW) / sourceW;
                            const scaleY = (bg.clientHeight || sourceH) / sourceH;
                            const maxX = Number(challenge.max_x || sourceW);
                            const maxY = Number(challenge.max_y || sourceH);
                            dragAnswer.x = clamp((clientX - rect.left) / scaleX - offsetX, 0, maxX);
                            dragAnswer.y = clamp((clientY - rect.top) / scaleY - offsetY, 0, maxY);
                            interacted = true;
                            renderPositions();
                        }
                        function start(clientX, clientY) {
                            const scaleX = (bg.clientWidth || sourceW) / sourceW;
                            const scaleY = (bg.clientHeight || sourceH) / sourceH;
                            offsetX = (clientX - piece.getBoundingClientRect().left) / scaleX;
                            offsetY = (clientY - piece.getBoundingClientRect().top) / scaleY;
                            dragging = true;
                        }
                        function end() { dragging = false; }
                        piece.addEventListener("mousedown", (e) => { e.preventDefault(); piece.style.cursor = "grabbing"; start(e.clientX, e.clientY); });
                        piece.addEventListener("touchstart", (e) => { const t = e.touches[0]; if (!t) return; e.preventDefault(); piece.style.cursor = "grabbing"; start(t.clientX, t.clientY); }, { passive:false });
                        document.addEventListener("mousemove", (e) => { if (dragging) updateFromClient(e.clientX, e.clientY); });
                        document.addEventListener("touchmove", (e) => { const t = e.touches[0]; if (!t || !dragging) return; updateFromClient(t.clientX, t.clientY); }, { passive:true });
                        document.addEventListener("mouseup", () => { end(); piece.style.cursor = "grab"; });
                        document.addEventListener("touchend", () => { end(); piece.style.cursor = "grab"; }, { passive:true });
                        bg.addEventListener("load", renderPositions);
                        window.addEventListener("resize", renderPositions);
                        renderPositions();
                    } else if (challenge.type === "rotate") {
                        const piece = document.getElementById("rotatePiece");
                        const step = Number(challenge.step || 10);
                        function renderRotation() {
                            if (piece) piece.style.transform = "rotate(" + rotateAnswer + "deg)";
                        }
                        document.getElementById("rotateLeft").addEventListener("click", () => {
                            interacted = true;
                            rotateAnswer = ((rotateAnswer - step) % 360 + 360) % 360;
                            renderRotation();
                        });
                        document.getElementById("rotateRight").addEventListener("click", () => {
                            interacted = true;
                            rotateAnswer = ((rotateAnswer + step) % 360 + 360) % 360;
                            renderRotation();
                        });
                        if (piece) {
                            piece.style.top = "0px";
                            piece.style.left = "0px";
                            piece.style.width = "100%";
                            piece.style.height = "100%";
                        }
                        renderRotation();
                    }
                    setVerifyVisualState();
                }
                try {
                    const wrapped = JSON.parse(atob("$encodedChallenge"));
                    if (wrapped && typeof wrapped === "object" && wrapped.web_context) {
                        webContext = wrapped.web_context || {};
                    } else {
                        webContext = wrapped || {};
                    }
                    seedBrowserStorage();
                    generateChallenge();
                } catch (error) {
                    showRenderError("Captcha render failed: " + (error && error.message ? error.message : String(error)));
                }
            </script>
        </body>
        </html>
    """.trimIndent()
}

@Composable
private fun ResourcePolicyFields(
    title: String,
    selectedMode: String,
    onModeChange: (String) -> Unit,
    waitMinutes: String,
    onWaitMinutesChange: (String) -> Unit,
) {
    Text(title, color = Color(0xFFFFC978), style = MaterialTheme.typography.titleSmall)
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        listOf("stop" to "Stop", "buy" to "Burn Token / Refill", "wait" to "Wait").forEach { (mode, label) ->
            OutlinedButton(
                onClick = { onModeChange(mode) },
                modifier = Modifier.weight(1f),
            ) {
                Text(if (selectedMode == mode) "$label *" else label)
            }
        }
    }
    OutlinedTextField(
        value = waitMinutes,
        onValueChange = onWaitMinutesChange,
        label = { Text("Wait Minutes") },
        singleLine = true,
        modifier = Modifier.fillMaxWidth(),
    )
}

@Composable
private fun NinjaSagaSettingsDialog(
    title: String,
    current: NinjaSagaSettingsUi,
    onDismiss: () -> Unit,
    onSave: (NinjaSagaSettingsUi) -> Unit,
) {
    var levelingDelay by rememberSaveable { mutableStateOf(current.levelingActionDelaySeconds.toString()) }
    var levelingCooldown by rememberSaveable { mutableStateOf(current.levelingCycleCooldownSeconds.toString()) }
    var levelingRestEvery by rememberSaveable { mutableStateOf(current.levelingRestEveryCycles.toString()) }
    var levelingRestDuration by rememberSaveable { mutableStateOf(current.levelingRestDurationSeconds.toString()) }
    var levelingJitter by rememberSaveable { mutableStateOf(current.levelingActionJitterSeconds.toString()) }
    var levelingMinCallDelay by rememberSaveable { mutableStateOf(current.levelingMinCallDelaySeconds.toString()) }
    var levelingStartRetryDelay by rememberSaveable { mutableStateOf(current.levelingStartRetryDelaySeconds.toString()) }
    var levelingStartMaxRetries by rememberSaveable { mutableStateOf(current.levelingStartMaxRetries.toString()) }
    var levelingCloudflareRest by rememberSaveable { mutableStateOf(current.levelingCloudflareRestSeconds.toString()) }
    var levelingCloudflareBackoffSteps by rememberSaveable { mutableStateOf(current.levelingCloudflareBackoffSteps) }
    var levelingFailureWindow by rememberSaveable { mutableStateOf(current.levelingFailureWindowSeconds.toString()) }
    var levelingMaxFailures by rememberSaveable { mutableStateOf(current.levelingMaxFailuresInWindow.toString()) }
    var levelingCircuitCooldown by rememberSaveable { mutableStateOf(current.levelingCircuitCooldownSeconds.toString()) }
    var eudemonDelay by rememberSaveable { mutableStateOf(current.eudemonStartFinishDelaySeconds.toString()) }
    var eudemonCooldown by rememberSaveable { mutableStateOf(current.eudemonCycleCooldownSeconds.toString()) }
    var sakuraBattleDelay by rememberSaveable { mutableStateOf(current.sakuraBattleDelaySeconds.toString()) }
    var eventResourceMode by rememberSaveable { mutableStateOf(current.eventResourceMode) }
    var eventWaitMinutes by rememberSaveable { mutableStateOf(current.eventWaitMinutes.toString()) }
    var specialJouninClassIndex by rememberSaveable { mutableStateOf(current.specialJouninClassIndex.coerceIn(1, 5)) }
    var tpTrainingAbuseLoop by rememberSaveable { mutableStateOf(current.tpTrainingAbuseLoop.toString()) }
    var ssTrainingAbuseLoop by rememberSaveable { mutableStateOf(current.ssTrainingAbuseLoop.toString()) }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(title) },
        text = {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .heightIn(max = 520.dp)
                    .verticalScroll(rememberScrollState()),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                OutlinedTextField(value = levelingDelay, onValueChange = { levelingDelay = it }, label = { Text("Leveling Action Delay (s)") }, singleLine = true)
                OutlinedTextField(value = levelingCooldown, onValueChange = { levelingCooldown = it }, label = { Text("Leveling Cooldown (s)") }, singleLine = true)
                OutlinedTextField(value = levelingRestEvery, onValueChange = { levelingRestEvery = it }, label = { Text("Rest Every N Cycles") }, singleLine = true)
                OutlinedTextField(value = levelingRestDuration, onValueChange = { levelingRestDuration = it }, label = { Text("Rest Duration (s)") }, singleLine = true)
                OutlinedTextField(value = levelingJitter, onValueChange = { levelingJitter = it }, label = { Text("Action Jitter (s)") }, singleLine = true)
                OutlinedTextField(value = levelingMinCallDelay, onValueChange = { levelingMinCallDelay = it }, label = { Text("Min Call Delay (s)") }, singleLine = true)
                OutlinedTextField(value = levelingStartRetryDelay, onValueChange = { levelingStartRetryDelay = it }, label = { Text("Start Retry Delay (s)") }, singleLine = true)
                OutlinedTextField(value = levelingStartMaxRetries, onValueChange = { levelingStartMaxRetries = it }, label = { Text("Start Max Retries") }, singleLine = true)
                OutlinedTextField(value = levelingCloudflareRest, onValueChange = { levelingCloudflareRest = it }, label = { Text("Cloudflare Base Rest (s)") }, singleLine = true)
                OutlinedTextField(value = levelingCloudflareBackoffSteps, onValueChange = { levelingCloudflareBackoffSteps = it }, label = { Text("Cloudflare Backoff Steps") }, singleLine = true)
                OutlinedTextField(value = levelingFailureWindow, onValueChange = { levelingFailureWindow = it }, label = { Text("Failure Window (s)") }, singleLine = true)
                OutlinedTextField(value = levelingMaxFailures, onValueChange = { levelingMaxFailures = it }, label = { Text("Max Failures In Window") }, singleLine = true)
                OutlinedTextField(value = levelingCircuitCooldown, onValueChange = { levelingCircuitCooldown = it }, label = { Text("Circuit Cooldown (s)") }, singleLine = true)
                OutlinedTextField(value = eudemonDelay, onValueChange = { eudemonDelay = it }, label = { Text("Eudemon Start/Finish Delay (s)") }, singleLine = true)
                OutlinedTextField(value = eudemonCooldown, onValueChange = { eudemonCooldown = it }, label = { Text("Eudemon Cooldown (s)") }, singleLine = true)
                Text("Special Jounin Class Skill")
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    OutlinedButton(onClick = { specialJouninClassIndex = 1 }) { Text("Intelligence") }
                    OutlinedButton(onClick = { specialJouninClassIndex = 2 }) { Text("Assault") }
                    OutlinedButton(onClick = { specialJouninClassIndex = 3 }) { Text("Sensation") }
                }
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    OutlinedButton(onClick = { specialJouninClassIndex = 4 }) { Text("Offense") }
                    OutlinedButton(onClick = { specialJouninClassIndex = 5 }) { Text("Medical") }
                }
                Text(
                    when (specialJouninClassIndex) {
                        1 -> "Selected: Intelligence Class Jutsu (skill2002)"
                        2 -> "Selected: Assault Class Jutsu (skill2004)"
                        3 -> "Selected: Sensation Class Jutsu (skill2001)"
                        4 -> "Selected: Offense Class Jutsu (skill2003)"
                        else -> "Selected: Medical Class Jutsu (skill2000)"
                    },
                )
                OutlinedTextField(
                    value = tpTrainingAbuseLoop,
                    onValueChange = { tpTrainingAbuseLoop = it },
                    label = { Text("TP Training Abuse Loop") },
                    singleLine = true,
                )
                OutlinedTextField(
                    value = ssTrainingAbuseLoop,
                    onValueChange = { ssTrainingAbuseLoop = it },
                    label = { Text("SS Training Abuse Bug Loop") },
                    singleLine = true,
                )
                ResourcePolicyFields(
                    title = "Event Empty Stamina/Energy",
                    selectedMode = eventResourceMode,
                    onModeChange = { eventResourceMode = it },
                    waitMinutes = eventWaitMinutes,
                    onWaitMinutesChange = { eventWaitMinutes = it },
                )
                OutlinedTextField(
                    value = sakuraBattleDelay,
                    onValueChange = { sakuraBattleDelay = it },
                    label = { Text("Sakura Battle Delay (s)") },
                    singleLine = true,
                )
            }
        },
        confirmButton = {
            Button(
                onClick = {
                    val next = NinjaSagaSettingsUi(
                        levelingActionDelaySeconds = levelingDelay.toIntOrNull() ?: current.levelingActionDelaySeconds,
                        levelingCycleCooldownSeconds = levelingCooldown.toIntOrNull() ?: current.levelingCycleCooldownSeconds,
                        levelingRestEveryCycles = levelingRestEvery.toIntOrNull() ?: current.levelingRestEveryCycles,
                        levelingRestDurationSeconds = levelingRestDuration.toIntOrNull() ?: current.levelingRestDurationSeconds,
                        levelingActionJitterSeconds = levelingJitter.toIntOrNull() ?: current.levelingActionJitterSeconds,
                        levelingMinCallDelaySeconds = levelingMinCallDelay.toIntOrNull() ?: current.levelingMinCallDelaySeconds,
                        levelingStartRetryDelaySeconds = levelingStartRetryDelay.toIntOrNull() ?: current.levelingStartRetryDelaySeconds,
                        levelingStartMaxRetries = levelingStartMaxRetries.toIntOrNull() ?: current.levelingStartMaxRetries,
                        levelingCloudflareRestSeconds = levelingCloudflareRest.toIntOrNull() ?: current.levelingCloudflareRestSeconds,
                        levelingCloudflareBackoffSteps = levelingCloudflareBackoffSteps,
                        levelingFailureWindowSeconds = levelingFailureWindow.toIntOrNull() ?: current.levelingFailureWindowSeconds,
                        levelingMaxFailuresInWindow = levelingMaxFailures.toIntOrNull() ?: current.levelingMaxFailuresInWindow,
                        levelingCircuitCooldownSeconds = levelingCircuitCooldown.toIntOrNull() ?: current.levelingCircuitCooldownSeconds,
                        eudemonStartFinishDelaySeconds = eudemonDelay.toIntOrNull() ?: current.eudemonStartFinishDelaySeconds,
                        eudemonCycleCooldownSeconds = eudemonCooldown.toIntOrNull() ?: current.eudemonCycleCooldownSeconds,
                        easterBattleDelaySeconds = current.easterBattleDelaySeconds,
                        easterCycleCooldownSeconds = current.easterCycleCooldownSeconds,
                        sakuraBattleDelaySeconds = sakuraBattleDelay.toIntOrNull()?.coerceAtLeast(1) ?: current.sakuraBattleDelaySeconds,
                        easterAutoSpendEnabled = false,
                        easterAutoSpendMaxRefillsPerRun = 0,
                        easterAutoSpendBuyAmount = current.easterAutoSpendBuyAmount,
                        eventResourceMode = eventResourceMode.ifBlank { current.eventResourceMode },
                        eventWaitMinutes = eventWaitMinutes.toIntOrNull() ?: current.eventWaitMinutes,
                        specialJouninClassIndex = specialJouninClassIndex.coerceIn(1, 5),
                        tpTrainingAbuseLoop = tpTrainingAbuseLoop.toIntOrNull()?.coerceAtLeast(1) ?: current.tpTrainingAbuseLoop,
                        ssTrainingAbuseLoop = ssTrainingAbuseLoop.toIntOrNull()?.coerceAtLeast(1) ?: current.ssTrainingAbuseLoop,
                        clanWarAutoSpendToken = current.clanWarAutoSpendToken,
                        clanWarStaminaRefillSource = current.clanWarStaminaRefillSource.ifBlank { "auto" },
                        clanWarBleedingMode = current.clanWarBleedingMode,
                        clanWarManualRecruit = current.clanWarManualRecruit,
                        clanWarManualMemberIds = current.clanWarManualMemberIds,
                        clanWarTargetClanId = current.clanWarTargetClanId,
                        clanWarTargetClanName = current.clanWarTargetClanName,
                        clanWarBattleDelaySeconds = current.clanWarBattleDelaySeconds,
                        clanWarRefreshDelaySeconds = current.clanWarRefreshDelaySeconds,
                        clanWarBuyStaminaDelaySeconds = current.clanWarBuyStaminaDelaySeconds,
                        clanWarAmfCallDelaySeconds = current.clanWarAmfCallDelaySeconds,
                        clanWarPostCaptchaResumeDelaySeconds = current.clanWarPostCaptchaResumeDelaySeconds,
                        clanWarLowStaminaWaitMinutes = current.clanWarLowStaminaWaitMinutes,
                    )
                    onSave(next)
                },
            ) { Text("Save") }
        },
        dismissButton = {
            OutlinedButton(onClick = onDismiss) { Text("Cancel") }
        },
        containerColor = Color(0xFF15110F),
    )
}

private enum class HelpLang { ID, EN }

private data class SageSkillOption(
    val id: String,
    val label: String,
)

private val SAGE_SKILL_OPTIONS = listOf(
    SageSkillOption("skill_4001", "Sensation Class Jutsu"),
    SageSkillOption("skill_4002", "Intelligence Class Jutsu"),
    SageSkillOption("skill_4003", "Offense Class Jutsu"),
    SageSkillOption("skill_4004", "Assault Class Jutsu"),
    SageSkillOption("skill_4005", "None"),
)

private fun sageHelpText(lang: HelpLang, key: String): String {
    val id = mapOf(
        "sj_class_skill" to "Pilih jutsu class otomatis saat promosi Special Jounin selesai.",
        "exam_start_delay" to "Jeda sebelum request start exam atau start stage dikirim.",
        "exam_finish_delay" to "Jeda sebelum request finish exam atau finish stage dikirim.",
        "battle_delay" to "Durasi tunggu simulasi battle, di antara request start battle dan finish battle.",
        "post_finish_delay" to "Jeda tambahan setelah finishMission atau finishStage berhasil.",
        "auto_relogin_wait" to "Waktu tunggu sebelum auto relogin saat sesi bermasalah.",
        "infinite_rest_every" to "Setelah berapa misi pada mode loop tanpa batas sistem akan istirahat.",
        "infinite_rest_duration" to "Durasi istirahat otomatis untuk mode loop tanpa batas.",
        "limited_rest_every" to "Setelah berapa misi pada mode loop terbatas sistem akan istirahat.",
        "limited_rest_duration" to "Durasi istirahat otomatis untuk mode loop terbatas.",
        "min_call_delay" to "Jeda minimum antar request AMF agar tidak terlalu rapat.",
        "action_delay" to "Jeda umum antar aksi leveling biasa.",
        "cycle_cooldown" to "Cooldown tambahan setelah satu cycle selesai.",
        "action_jitter" to "Tambahan jeda acak supaya timing tidak terlalu kaku.",
        "rest_every_cycles" to "Istirahat umum setiap N cycle leveling.",
        "rest_duration" to "Durasi istirahat umum tiap cycle.",
        "start_retry_delay" to "Jeda sebelum retry saat startMission atau startStage gagal.",
        "start_max_retries" to "Maksimum retry startMission atau startStage per cycle.",
        "failure_window" to "Window hitung kegagalan runtime beruntun.",
        "max_failures" to "Jika kegagalan dalam window ini melebihi batas, action dipause.",
        "circuit_cooldown" to "Lama jeda saat pengaman kegagalan aktif.",
    )
    val en = mapOf(
        "sj_class_skill" to "Choose the class jutsu automatically when Special Jounin promotion finishes.",
        "exam_start_delay" to "Delay before sending the start exam or start stage request.",
        "exam_finish_delay" to "Delay before sending the finish exam or finish stage request.",
        "battle_delay" to "Simulated battle duration between the AMF battle start and battle finish requests.",
        "post_finish_delay" to "Extra delay after finishMission or finishStage succeeds.",
        "auto_relogin_wait" to "Wait time before auto relogin when the session has problems.",
        "infinite_rest_every" to "How many missions to run in infinite loop mode before auto rest.",
        "infinite_rest_duration" to "Auto rest duration for infinite loop mode.",
        "limited_rest_every" to "How many missions to run in limited loop mode before auto rest.",
        "limited_rest_duration" to "Auto rest duration for limited loop mode.",
        "min_call_delay" to "Minimum gap between AMF requests so calls are not too tight.",
        "action_delay" to "General pacing delay between regular leveling actions.",
        "cycle_cooldown" to "Extra cooldown after one leveling cycle finishes.",
        "action_jitter" to "Random extra delay so timing is less robotic.",
        "rest_every_cycles" to "General rest every N leveling cycles.",
        "rest_duration" to "General rest duration per cycle.",
        "start_retry_delay" to "Delay before retrying when startMission or startStage fails.",
        "start_max_retries" to "Maximum retries for startMission or startStage per cycle.",
        "failure_window" to "Rolling window used to count repeated runtime failures.",
        "max_failures" to "If failures inside that window exceed this value, the action pauses.",
        "circuit_cooldown" to "Cooldown length when the failure safety circuit is active.",
    )
    return (if (lang == HelpLang.ID) id else en)[key].orEmpty()
}

@Composable
private fun SageSettingField(
    label: String,
    helpKey: String,
    selectedHelpKey: String?,
    onToggleHelp: (String) -> Unit,
    helpLang: HelpLang,
    content: @Composable () -> Unit,
) {
    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(label, color = Color(0xFFEDE2D1), style = MaterialTheme.typography.bodyMedium)
            TextButton(onClick = { onToggleHelp(helpKey) }, contentPadding = PaddingValues(horizontal = 6.dp, vertical = 0.dp)) {
                Text("?", color = Color(0xFFFFC978))
            }
        }
        content()
        if (selectedHelpKey == helpKey) {
            Text(
                text = sageHelpText(helpLang, helpKey),
                color = Color(0xFFB8A98E),
                style = MaterialTheme.typography.bodySmall,
            )
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun SageSettingsDialog(
    current: SageSettingsUi,
    onDismiss: () -> Unit,
    onSave: (SageSettingsUi) -> Unit,
) {
    var helpLang by rememberSaveable { mutableStateOf(HelpLang.ID) }
    var selectedHelpKey by rememberSaveable { mutableStateOf<String?>(null) }
    var generalActionDelay by rememberSaveable { mutableStateOf(current.generalActionDelaySeconds.toString()) }
    var cycleCooldown by rememberSaveable { mutableStateOf(current.cycleCooldownSeconds.toString()) }
    var restEveryCycles by rememberSaveable { mutableStateOf(current.restEveryCycles.toString()) }
    var restDuration by rememberSaveable { mutableStateOf(current.restDurationSeconds.toString()) }
    var actionJitter by rememberSaveable { mutableStateOf(current.actionJitterSeconds.toString()) }
    var minCallDelay by rememberSaveable { mutableStateOf(current.minCallDelaySeconds.toString()) }
    var startRetryDelay by rememberSaveable { mutableStateOf(current.startRetryDelaySeconds.toString()) }
    var startMaxRetries by rememberSaveable { mutableStateOf(current.startMaxRetries.toString()) }
    var failureWindow by rememberSaveable { mutableStateOf(current.failureWindowSeconds.toString()) }
    var maxFailures by rememberSaveable { mutableStateOf(current.maxFailuresInWindow.toString()) }
    var circuitCooldown by rememberSaveable { mutableStateOf(current.circuitCooldownSeconds.toString()) }
    var examStartDelay by rememberSaveable { mutableStateOf(current.examStartDelaySeconds.toString()) }
    var examFinishDelay by rememberSaveable { mutableStateOf(current.examFinishDelaySeconds.toString()) }
    var battleDurationDelay by rememberSaveable { mutableStateOf(current.battleDurationDelaySeconds.toString()) }
    var afterFinishDelay by rememberSaveable { mutableStateOf(current.afterFinishDelaySeconds.toString()) }
    var autoReloginWait by rememberSaveable { mutableStateOf(current.autoReloginWaitSeconds.toString()) }
    var infiniteLoopRestEvery by rememberSaveable { mutableStateOf(current.infiniteLoopRestEveryMissions.toString()) }
    var infiniteLoopRestDuration by rememberSaveable { mutableStateOf(current.infiniteLoopRestDurationSeconds.toString()) }
    var limitedLoopRestEvery by rememberSaveable { mutableStateOf(current.limitedLoopRestEveryMissions.toString()) }
    var limitedLoopRestDuration by rememberSaveable { mutableStateOf(current.limitedLoopRestDurationSeconds.toString()) }
    var specialJouninSkill by rememberSaveable { mutableStateOf(current.specialJouninClassSkill) }
    var specialSkillExpanded by remember { mutableStateOf(false) }
    var eventResourceMode by rememberSaveable { mutableStateOf(current.eventResourceMode) }
    var eventWaitMinutes by rememberSaveable { mutableStateOf(current.eventWaitMinutes.toString()) }
    var anivEventResourceMode by rememberSaveable { mutableStateOf(current.anivEventResourceMode) }
    var anivEventWaitMinutes by rememberSaveable { mutableStateOf(current.anivEventWaitMinutes.toString()) }
    var sakuraEventResourceMode by rememberSaveable { mutableStateOf(current.sakuraEventResourceMode) }
    var sakuraEventWaitMinutes by rememberSaveable { mutableStateOf(current.sakuraEventWaitMinutes.toString()) }
    var easterEventResourceMode by rememberSaveable { mutableStateOf(current.easterEventResourceMode) }
    var easterEventWaitMinutes by rememberSaveable { mutableStateOf(current.easterEventWaitMinutes.toString()) }
    var shadowWarResourceMode by rememberSaveable { mutableStateOf(current.shadowWarResourceMode) }
    var shadowWarWaitMinutes by rememberSaveable { mutableStateOf(current.shadowWarWaitMinutes.toString()) }
    var clanWarAutoSpendToken by rememberSaveable { mutableStateOf(current.clanWarAutoSpendToken) }
    var clanWarStaminaRefillSource by rememberSaveable { mutableStateOf(current.clanWarStaminaRefillSource.ifBlank { "auto" }) }
    var clanWarBattleDelay by rememberSaveable { mutableStateOf(current.clanWarBattleDelaySeconds.toString()) }
    var clanWarBuyStaminaDelay by rememberSaveable { mutableStateOf(current.clanWarBuyStaminaDelaySeconds.toString()) }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Ninja Sage Settings") },
        text = {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .heightIn(max = 520.dp)
                    .verticalScroll(rememberScrollState()),
                verticalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    OutlinedButton(
                        onClick = { helpLang = HelpLang.ID },
                        modifier = Modifier.weight(1f),
                    ) { Text("Indonesia") }
                    OutlinedButton(
                        onClick = { helpLang = HelpLang.EN },
                        modifier = Modifier.weight(1f),
                    ) { Text("English") }
                }

                SageSettingField("Special Jounin Auto Class Jutsu", "sj_class_skill", selectedHelpKey, { selectedHelpKey = if (selectedHelpKey == it) null else it }, helpLang) {
                    ExposedDropdownMenuBox(
                        expanded = specialSkillExpanded,
                        onExpandedChange = { specialSkillExpanded = !specialSkillExpanded },
                    ) {
                        val selectedLabel = SAGE_SKILL_OPTIONS.firstOrNull { it.id == specialJouninSkill }?.label
                            ?: specialJouninSkill
                        OutlinedTextField(
                            value = selectedLabel,
                            onValueChange = {},
                            readOnly = true,
                            modifier = Modifier
                                .menuAnchor()
                                .fillMaxWidth(),
                            trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = specialSkillExpanded) },
                            singleLine = true,
                        )
                        DropdownMenu(
                            expanded = specialSkillExpanded,
                            onDismissRequest = { specialSkillExpanded = false },
                        ) {
                            SAGE_SKILL_OPTIONS.forEach { option ->
                                DropdownMenuItem(
                                    text = { Text("${option.label} (${option.id})") },
                                    onClick = {
                                        specialJouninSkill = option.id
                                        specialSkillExpanded = false
                                    },
                                )
                            }
                        }
                    }
                }
                SageSettingField("Exam Start Request Delay (s)", "exam_start_delay", selectedHelpKey, { selectedHelpKey = if (selectedHelpKey == it) null else it }, helpLang) {
                    OutlinedTextField(value = examStartDelay, onValueChange = { examStartDelay = it }, singleLine = true, modifier = Modifier.fillMaxWidth())
                }
                SageSettingField("Exam Finish Request Delay (s)", "exam_finish_delay", selectedHelpKey, { selectedHelpKey = if (selectedHelpKey == it) null else it }, helpLang) {
                    OutlinedTextField(value = examFinishDelay, onValueChange = { examFinishDelay = it }, singleLine = true, modifier = Modifier.fillMaxWidth())
                }
                SageSettingField("Battle Duration Delay (s)", "battle_delay", selectedHelpKey, { selectedHelpKey = if (selectedHelpKey == it) null else it }, helpLang) {
                    OutlinedTextField(value = battleDurationDelay, onValueChange = { battleDurationDelay = it }, singleLine = true, modifier = Modifier.fillMaxWidth())
                }
                SageSettingField("After Finish Delay (s)", "post_finish_delay", selectedHelpKey, { selectedHelpKey = if (selectedHelpKey == it) null else it }, helpLang) {
                    OutlinedTextField(value = afterFinishDelay, onValueChange = { afterFinishDelay = it }, singleLine = true, modifier = Modifier.fillMaxWidth())
                }
                SageSettingField("Auto Relogin Wait (s)", "auto_relogin_wait", selectedHelpKey, { selectedHelpKey = if (selectedHelpKey == it) null else it }, helpLang) {
                    OutlinedTextField(value = autoReloginWait, onValueChange = { autoReloginWait = it }, singleLine = true, modifier = Modifier.fillMaxWidth())
                }
                SageSettingField("Infinite Loop Rest Every N Missions", "infinite_rest_every", selectedHelpKey, { selectedHelpKey = if (selectedHelpKey == it) null else it }, helpLang) {
                    OutlinedTextField(value = infiniteLoopRestEvery, onValueChange = { infiniteLoopRestEvery = it }, singleLine = true, modifier = Modifier.fillMaxWidth())
                }
                SageSettingField("Infinite Loop Rest Duration (s)", "infinite_rest_duration", selectedHelpKey, { selectedHelpKey = if (selectedHelpKey == it) null else it }, helpLang) {
                    OutlinedTextField(value = infiniteLoopRestDuration, onValueChange = { infiniteLoopRestDuration = it }, singleLine = true, modifier = Modifier.fillMaxWidth())
                }
                SageSettingField("Limited Loop Rest Every N Missions", "limited_rest_every", selectedHelpKey, { selectedHelpKey = if (selectedHelpKey == it) null else it }, helpLang) {
                    OutlinedTextField(value = limitedLoopRestEvery, onValueChange = { limitedLoopRestEvery = it }, singleLine = true, modifier = Modifier.fillMaxWidth())
                }
                SageSettingField("Limited Loop Rest Duration (s)", "limited_rest_duration", selectedHelpKey, { selectedHelpKey = if (selectedHelpKey == it) null else it }, helpLang) {
                    OutlinedTextField(value = limitedLoopRestDuration, onValueChange = { limitedLoopRestDuration = it }, singleLine = true, modifier = Modifier.fillMaxWidth())
                }
                SageSettingField("Min Call Delay (s)", "min_call_delay", selectedHelpKey, { selectedHelpKey = if (selectedHelpKey == it) null else it }, helpLang) {
                    OutlinedTextField(value = minCallDelay, onValueChange = { minCallDelay = it }, singleLine = true, modifier = Modifier.fillMaxWidth())
                }
                SageSettingField("General Action Delay (s)", "action_delay", selectedHelpKey, { selectedHelpKey = if (selectedHelpKey == it) null else it }, helpLang) {
                    OutlinedTextField(value = generalActionDelay, onValueChange = { generalActionDelay = it }, singleLine = true, modifier = Modifier.fillMaxWidth())
                }
                SageSettingField("Cycle Cooldown (s)", "cycle_cooldown", selectedHelpKey, { selectedHelpKey = if (selectedHelpKey == it) null else it }, helpLang) {
                    OutlinedTextField(value = cycleCooldown, onValueChange = { cycleCooldown = it }, singleLine = true, modifier = Modifier.fillMaxWidth())
                }
                SageSettingField("Action Jitter (s)", "action_jitter", selectedHelpKey, { selectedHelpKey = if (selectedHelpKey == it) null else it }, helpLang) {
                    OutlinedTextField(value = actionJitter, onValueChange = { actionJitter = it }, singleLine = true, modifier = Modifier.fillMaxWidth())
                }
                SageSettingField("Rest Every N Cycles", "rest_every_cycles", selectedHelpKey, { selectedHelpKey = if (selectedHelpKey == it) null else it }, helpLang) {
                    OutlinedTextField(value = restEveryCycles, onValueChange = { restEveryCycles = it }, singleLine = true, modifier = Modifier.fillMaxWidth())
                }
                SageSettingField("Rest Duration (s)", "rest_duration", selectedHelpKey, { selectedHelpKey = if (selectedHelpKey == it) null else it }, helpLang) {
                    OutlinedTextField(value = restDuration, onValueChange = { restDuration = it }, singleLine = true, modifier = Modifier.fillMaxWidth())
                }
                SageSettingField("Start Retry Delay (s)", "start_retry_delay", selectedHelpKey, { selectedHelpKey = if (selectedHelpKey == it) null else it }, helpLang) {
                    OutlinedTextField(value = startRetryDelay, onValueChange = { startRetryDelay = it }, singleLine = true, modifier = Modifier.fillMaxWidth())
                }
                SageSettingField("Start Max Retries", "start_max_retries", selectedHelpKey, { selectedHelpKey = if (selectedHelpKey == it) null else it }, helpLang) {
                    OutlinedTextField(value = startMaxRetries, onValueChange = { startMaxRetries = it }, singleLine = true, modifier = Modifier.fillMaxWidth())
                }
                SageSettingField("Failure Window (s)", "failure_window", selectedHelpKey, { selectedHelpKey = if (selectedHelpKey == it) null else it }, helpLang) {
                    OutlinedTextField(value = failureWindow, onValueChange = { failureWindow = it }, singleLine = true, modifier = Modifier.fillMaxWidth())
                }
                SageSettingField("Max Failures In Window", "max_failures", selectedHelpKey, { selectedHelpKey = if (selectedHelpKey == it) null else it }, helpLang) {
                    OutlinedTextField(value = maxFailures, onValueChange = { maxFailures = it }, singleLine = true, modifier = Modifier.fillMaxWidth())
                }
                SageSettingField("Circuit Cooldown (s)", "circuit_cooldown", selectedHelpKey, { selectedHelpKey = if (selectedHelpKey == it) null else it }, helpLang) {
                    OutlinedTextField(value = circuitCooldown, onValueChange = { circuitCooldown = it }, singleLine = true, modifier = Modifier.fillMaxWidth())
                }
                ResourcePolicyFields(
                    title = "Event Empty Stamina/Energy",
                    selectedMode = eventResourceMode,
                    onModeChange = { eventResourceMode = it },
                    waitMinutes = eventWaitMinutes,
                    onWaitMinutesChange = { eventWaitMinutes = it },
                )
                ResourcePolicyFields(
                    title = "Anniversary Empty Stamina/Energy",
                    selectedMode = anivEventResourceMode,
                    onModeChange = { anivEventResourceMode = it },
                    waitMinutes = anivEventWaitMinutes,
                    onWaitMinutesChange = { anivEventWaitMinutes = it },
                )
                ResourcePolicyFields(
                    title = "Sakura Empty Stamina/Energy",
                    selectedMode = sakuraEventResourceMode,
                    onModeChange = { sakuraEventResourceMode = it },
                    waitMinutes = sakuraEventWaitMinutes,
                    onWaitMinutesChange = { sakuraEventWaitMinutes = it },
                )
                ResourcePolicyFields(
                    title = "Easter Empty Stamina/Energy",
                    selectedMode = easterEventResourceMode,
                    onModeChange = { easterEventResourceMode = it },
                    waitMinutes = easterEventWaitMinutes,
                    onWaitMinutesChange = { easterEventWaitMinutes = it },
                )
                ResourcePolicyFields(
                    title = "Shadow War Empty Stamina/Energy",
                    selectedMode = shadowWarResourceMode,
                    onModeChange = { shadowWarResourceMode = it },
                    waitMinutes = shadowWarWaitMinutes,
                    onWaitMinutesChange = { shadowWarWaitMinutes = it },
                )
                Text("Clan War", color = Color(0xFFFFC978), style = MaterialTheme.typography.titleSmall)
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Checkbox(checked = clanWarAutoSpendToken, onCheckedChange = { clanWarAutoSpendToken = it })
                    Text("Auto Refill Stamina")
                }
                Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedButton(onClick = { clanWarStaminaRefillSource = "auto" }, modifier = Modifier.weight(1f)) {
                        Text(if (clanWarStaminaRefillSource == "auto") "Auto *" else "Auto")
                    }
                    OutlinedButton(onClick = { clanWarStaminaRefillSource = "token" }, modifier = Modifier.weight(1f)) {
                        Text(if (clanWarStaminaRefillSource == "token") "Token *" else "Token")
                    }
                    OutlinedButton(onClick = { clanWarStaminaRefillSource = "roll" }, modifier = Modifier.weight(1f)) {
                        Text(if (clanWarStaminaRefillSource == "roll") "Onigiri *" else "Onigiri")
                    }
                }
                SageSettingField("Clan War Battle Delay (s)", "clan_war_battle_delay", selectedHelpKey, { selectedHelpKey = if (selectedHelpKey == it) null else it }, helpLang) {
                    OutlinedTextField(value = clanWarBattleDelay, onValueChange = { clanWarBattleDelay = it }, singleLine = true, modifier = Modifier.fillMaxWidth())
                }
                SageSettingField("Clan War Buy Stamina Delay (s)", "clan_war_buy_delay", selectedHelpKey, { selectedHelpKey = if (selectedHelpKey == it) null else it }, helpLang) {
                    OutlinedTextField(value = clanWarBuyStaminaDelay, onValueChange = { clanWarBuyStaminaDelay = it }, singleLine = true, modifier = Modifier.fillMaxWidth())
                }
            }
        },
        confirmButton = {
            Button(
                onClick = {
                    onSave(
                        SageSettingsUi(
                            generalActionDelaySeconds = generalActionDelay.toIntOrNull() ?: current.generalActionDelaySeconds,
                            cycleCooldownSeconds = cycleCooldown.toIntOrNull() ?: current.cycleCooldownSeconds,
                            restEveryCycles = restEveryCycles.toIntOrNull() ?: current.restEveryCycles,
                            restDurationSeconds = restDuration.toIntOrNull() ?: current.restDurationSeconds,
                            actionJitterSeconds = actionJitter.toIntOrNull() ?: current.actionJitterSeconds,
                            minCallDelaySeconds = minCallDelay.toIntOrNull() ?: current.minCallDelaySeconds,
                            startRetryDelaySeconds = startRetryDelay.toIntOrNull() ?: current.startRetryDelaySeconds,
                            startMaxRetries = startMaxRetries.toIntOrNull() ?: current.startMaxRetries,
                            failureWindowSeconds = failureWindow.toIntOrNull() ?: current.failureWindowSeconds,
                            maxFailuresInWindow = maxFailures.toIntOrNull() ?: current.maxFailuresInWindow,
                            circuitCooldownSeconds = circuitCooldown.toIntOrNull() ?: current.circuitCooldownSeconds,
                            examStartDelaySeconds = examStartDelay.toIntOrNull() ?: current.examStartDelaySeconds,
                            examFinishDelaySeconds = examFinishDelay.toIntOrNull() ?: current.examFinishDelaySeconds,
                            battleDurationDelaySeconds = battleDurationDelay.toIntOrNull() ?: current.battleDurationDelaySeconds,
                            afterFinishDelaySeconds = afterFinishDelay.toIntOrNull() ?: current.afterFinishDelaySeconds,
                            autoReloginWaitSeconds = autoReloginWait.toIntOrNull() ?: current.autoReloginWaitSeconds,
                            infiniteLoopRestEveryMissions = infiniteLoopRestEvery.toIntOrNull() ?: current.infiniteLoopRestEveryMissions,
                            infiniteLoopRestDurationSeconds = infiniteLoopRestDuration.toIntOrNull() ?: current.infiniteLoopRestDurationSeconds,
                            limitedLoopRestEveryMissions = limitedLoopRestEvery.toIntOrNull() ?: current.limitedLoopRestEveryMissions,
                            limitedLoopRestDurationSeconds = limitedLoopRestDuration.toIntOrNull() ?: current.limitedLoopRestDurationSeconds,
                            specialJouninClassSkill = specialJouninSkill.ifBlank { current.specialJouninClassSkill },
                            eventResourceMode = eventResourceMode.ifBlank { current.eventResourceMode },
                            eventWaitMinutes = eventWaitMinutes.toIntOrNull() ?: current.eventWaitMinutes,
                            anivEventResourceMode = anivEventResourceMode.ifBlank { current.anivEventResourceMode },
                            anivEventWaitMinutes = anivEventWaitMinutes.toIntOrNull() ?: current.anivEventWaitMinutes,
                            sakuraEventResourceMode = sakuraEventResourceMode.ifBlank { current.sakuraEventResourceMode },
                            sakuraEventWaitMinutes = sakuraEventWaitMinutes.toIntOrNull() ?: current.sakuraEventWaitMinutes,
                            easterEventResourceMode = easterEventResourceMode.ifBlank { current.easterEventResourceMode },
                            easterEventWaitMinutes = easterEventWaitMinutes.toIntOrNull() ?: current.easterEventWaitMinutes,
                            shadowWarResourceMode = shadowWarResourceMode.ifBlank { current.shadowWarResourceMode },
                            shadowWarWaitMinutes = shadowWarWaitMinutes.toIntOrNull() ?: current.shadowWarWaitMinutes,
                            clanWarAutoSpendToken = clanWarAutoSpendToken,
                            clanWarStaminaRefillSource = clanWarStaminaRefillSource.ifBlank { "auto" },
                            clanWarBattleDelaySeconds = clanWarBattleDelay.toIntOrNull() ?: current.clanWarBattleDelaySeconds,
                            clanWarBuyStaminaDelaySeconds = clanWarBuyStaminaDelay.toIntOrNull() ?: current.clanWarBuyStaminaDelaySeconds,
                        )
                    )
                },
            ) { Text("Save") }
        },
        dismissButton = {
            OutlinedButton(onClick = onDismiss) { Text("Cancel") }
        },
        containerColor = Color(0xFF15110F),
    )
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun RiftSettingsDialog(
    current: RiftSettingsUi,
    skillOptions: List<RiftSkillOption>,
    onDismiss: () -> Unit,
    onSave: (RiftSettingsUi) -> Unit,
) {
    var minCallDelay by rememberSaveable { mutableStateOf(current.minCallDelaySeconds.toString()) }
    var loopDelay by rememberSaveable { mutableStateOf(current.loopDelaySeconds.toString()) }
    var autoReloginWait by rememberSaveable { mutableStateOf(current.autoReloginWaitSeconds.toString()) }
    var infiniteRestEvery by rememberSaveable { mutableStateOf(current.infiniteLoopRestEveryCycles.toString()) }
    var infiniteRestDuration by rememberSaveable { mutableStateOf(current.infiniteLoopRestDurationSeconds.toString()) }
    var limitedRestEvery by rememberSaveable { mutableStateOf(current.limitedLoopRestEveryCycles.toString()) }
    var limitedRestDuration by rememberSaveable { mutableStateOf(current.limitedLoopRestDurationSeconds.toString()) }
    var missionBaseWait by rememberSaveable { mutableStateOf(current.missionBattleWaitBaseSeconds.toString()) }
    var missionRandomWait by rememberSaveable { mutableStateOf(current.missionBattleWaitRandomSeconds.toString()) }
    var eventBaseWait by rememberSaveable { mutableStateOf(current.eventBattleWaitBaseSeconds.toString()) }
    var eventRandomWait by rememberSaveable { mutableStateOf(current.eventBattleWaitRandomSeconds.toString()) }
    var eudemonBaseWait by rememberSaveable { mutableStateOf(current.eudemonBattleWaitBaseSeconds.toString()) }
    var eudemonRandomWait by rememberSaveable { mutableStateOf(current.eudemonBattleWaitRandomSeconds.toString()) }
    var eudemonBetweenDelay by rememberSaveable { mutableStateOf(current.eudemonBetweenBattlesDelaySeconds.toString()) }
    var huntingBaseWait by rememberSaveable { mutableStateOf(current.huntingHouseBattleWaitBaseSeconds.toString()) }
    var huntingRandomWait by rememberSaveable { mutableStateOf(current.huntingHouseBattleWaitRandomSeconds.toString()) }
    var huntingBetweenDelay by rememberSaveable { mutableStateOf(current.huntingHouseBetweenBattlesDelaySeconds.toString()) }
    var examMinWait by rememberSaveable { mutableStateOf(current.examWaitMinSeconds.toString()) }
    var examMaxWait by rememberSaveable { mutableStateOf(current.examWaitMaxSeconds.toString()) }
    var examStageGap by rememberSaveable { mutableStateOf(current.examStageGapSeconds.toString()) }
    var specialJouninSkill by rememberSaveable { mutableStateOf(current.specialJouninClassSkill) }
    var skillExpanded by remember { mutableStateOf(false) }
    var eventResourceMode by rememberSaveable { mutableStateOf(current.eventResourceMode) }
    var eventWaitMinutes by rememberSaveable { mutableStateOf(current.eventWaitMinutes.toString()) }
    var easterEventResourceMode by rememberSaveable { mutableStateOf(current.easterEventResourceMode) }
    var easterEventWaitMinutes by rememberSaveable { mutableStateOf(current.easterEventWaitMinutes.toString()) }
    val resolvedSkillOptions = if (skillOptions.isNotEmpty()) skillOptions else listOf(
        RiftSkillOption("skill_2002", "Intelligence Class"),
        RiftSkillOption("skill_2004", "Surprise Attack Class"),
        RiftSkillOption("skill_2001", "Sensor Class"),
        RiftSkillOption("skill_2003", "Heavy Attack Class"),
        RiftSkillOption("skill_2000", "Medical Class"),
    )

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Ninja Rift Settings") },
        text = {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .heightIn(max = 520.dp)
                    .verticalScroll(rememberScrollState()),
                verticalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                Text("Main pacing", color = Color(0xFFFFC978), style = MaterialTheme.typography.titleMedium)
                OutlinedTextField(value = minCallDelay, onValueChange = { minCallDelay = it }, singleLine = true, modifier = Modifier.fillMaxWidth(), label = { Text("Min Call Delay (s)") })
                OutlinedTextField(value = loopDelay, onValueChange = { loopDelay = it }, singleLine = true, modifier = Modifier.fillMaxWidth(), label = { Text("Loop Delay (s)") })
                OutlinedTextField(value = autoReloginWait, onValueChange = { autoReloginWait = it }, singleLine = true, modifier = Modifier.fillMaxWidth(), label = { Text("Auto Relogin Wait (s)") })
                OutlinedTextField(value = infiniteRestEvery, onValueChange = { infiniteRestEvery = it }, singleLine = true, modifier = Modifier.fillMaxWidth(), label = { Text("Infinite Loop Rest Every N Cycles") })
                OutlinedTextField(value = infiniteRestDuration, onValueChange = { infiniteRestDuration = it }, singleLine = true, modifier = Modifier.fillMaxWidth(), label = { Text("Infinite Loop Rest Duration (s)") })
                OutlinedTextField(value = limitedRestEvery, onValueChange = { limitedRestEvery = it }, singleLine = true, modifier = Modifier.fillMaxWidth(), label = { Text("Limited Loop Rest Every N Cycles") })
                OutlinedTextField(value = limitedRestDuration, onValueChange = { limitedRestDuration = it }, singleLine = true, modifier = Modifier.fillMaxWidth(), label = { Text("Limited Loop Rest Duration (s)") })

                Text("Mission battle", color = Color(0xFFFFC978), style = MaterialTheme.typography.titleMedium)
                OutlinedTextField(value = missionBaseWait, onValueChange = { missionBaseWait = it }, singleLine = true, modifier = Modifier.fillMaxWidth(), label = { Text("Mission Battle Base Wait (s)") })
                OutlinedTextField(value = missionRandomWait, onValueChange = { missionRandomWait = it }, singleLine = true, modifier = Modifier.fillMaxWidth(), label = { Text("Mission Battle Random Wait (s)") })

                Text("Event battle", color = Color(0xFFFFC978), style = MaterialTheme.typography.titleMedium)
                OutlinedTextField(value = eventBaseWait, onValueChange = { eventBaseWait = it }, singleLine = true, modifier = Modifier.fillMaxWidth(), label = { Text("Event Battle Base Wait (s)") })
                OutlinedTextField(value = eventRandomWait, onValueChange = { eventRandomWait = it }, singleLine = true, modifier = Modifier.fillMaxWidth(), label = { Text("Event Battle Random Wait (s)") })
                ResourcePolicyFields(
                    title = "Event Empty Stamina/Energy",
                    selectedMode = eventResourceMode,
                    onModeChange = { eventResourceMode = it },
                    waitMinutes = eventWaitMinutes,
                    onWaitMinutesChange = { eventWaitMinutes = it },
                )
                ResourcePolicyFields(
                    title = "Easter Empty Stamina/Energy",
                    selectedMode = easterEventResourceMode,
                    onModeChange = { easterEventResourceMode = it },
                    waitMinutes = easterEventWaitMinutes,
                    onWaitMinutesChange = { easterEventWaitMinutes = it },
                )

                Text("Eudemon Garden", color = Color(0xFFFFC978), style = MaterialTheme.typography.titleMedium)
                OutlinedTextField(value = eudemonBaseWait, onValueChange = { eudemonBaseWait = it }, singleLine = true, modifier = Modifier.fillMaxWidth(), label = { Text("Eudemon Battle Base Wait (s)") })
                OutlinedTextField(value = eudemonRandomWait, onValueChange = { eudemonRandomWait = it }, singleLine = true, modifier = Modifier.fillMaxWidth(), label = { Text("Eudemon Battle Random Wait (s)") })
                OutlinedTextField(value = eudemonBetweenDelay, onValueChange = { eudemonBetweenDelay = it }, singleLine = true, modifier = Modifier.fillMaxWidth(), label = { Text("Eudemon Between Battles Delay (s)") })

                Text("Hunting House", color = Color(0xFFFFC978), style = MaterialTheme.typography.titleMedium)
                OutlinedTextField(value = huntingBaseWait, onValueChange = { huntingBaseWait = it }, singleLine = true, modifier = Modifier.fillMaxWidth(), label = { Text("Hunting House Base Wait (s)") })
                OutlinedTextField(value = huntingRandomWait, onValueChange = { huntingRandomWait = it }, singleLine = true, modifier = Modifier.fillMaxWidth(), label = { Text("Hunting House Random Wait (s)") })
                OutlinedTextField(value = huntingBetweenDelay, onValueChange = { huntingBetweenDelay = it }, singleLine = true, modifier = Modifier.fillMaxWidth(), label = { Text("Hunting House Between Battles Delay (s)") })

                Text("Exam", color = Color(0xFFFFC978), style = MaterialTheme.typography.titleMedium)
                OutlinedTextField(value = examMinWait, onValueChange = { examMinWait = it }, singleLine = true, modifier = Modifier.fillMaxWidth(), label = { Text("Exam Min Delay (s)") })
                OutlinedTextField(value = examMaxWait, onValueChange = { examMaxWait = it }, singleLine = true, modifier = Modifier.fillMaxWidth(), label = { Text("Exam Max Delay (s)") })
                OutlinedTextField(value = examStageGap, onValueChange = { examStageGap = it }, singleLine = true, modifier = Modifier.fillMaxWidth(), label = { Text("Exam Stage Gap (s)") })

                Text("Special Jounin", color = Color(0xFFFFC978), style = MaterialTheme.typography.titleMedium)
                ExposedDropdownMenuBox(
                    expanded = skillExpanded,
                    onExpandedChange = { skillExpanded = !skillExpanded },
                ) {
                    val selectedLabel = resolvedSkillOptions.firstOrNull { it.id == specialJouninSkill }?.label
                        ?: specialJouninSkill
                    OutlinedTextField(
                        value = selectedLabel,
                        onValueChange = {},
                        readOnly = true,
                        modifier = Modifier
                            .menuAnchor()
                            .fillMaxWidth(),
                        trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = skillExpanded) },
                        singleLine = true,
                        label = { Text("Special Jounin Class") },
                    )
                    DropdownMenu(
                        expanded = skillExpanded,
                        onDismissRequest = { skillExpanded = false },
                    ) {
                        resolvedSkillOptions.forEach { option ->
                            DropdownMenuItem(
                                text = { Text("${option.label} (${option.id})") },
                                onClick = {
                                    specialJouninSkill = option.id
                                    skillExpanded = false
                                },
                            )
                        }
                    }
                }
            }
        },
        confirmButton = {
            Button(
                onClick = {
                    onSave(
                        RiftSettingsUi(
                            minCallDelaySeconds = minCallDelay.toIntOrNull() ?: current.minCallDelaySeconds,
                            loopDelaySeconds = loopDelay.toIntOrNull() ?: current.loopDelaySeconds,
                            autoReloginWaitSeconds = autoReloginWait.toIntOrNull() ?: current.autoReloginWaitSeconds,
                            infiniteLoopRestEveryCycles = infiniteRestEvery.toIntOrNull() ?: current.infiniteLoopRestEveryCycles,
                            infiniteLoopRestDurationSeconds = infiniteRestDuration.toIntOrNull() ?: current.infiniteLoopRestDurationSeconds,
                            limitedLoopRestEveryCycles = limitedRestEvery.toIntOrNull() ?: current.limitedLoopRestEveryCycles,
                            limitedLoopRestDurationSeconds = limitedRestDuration.toIntOrNull() ?: current.limitedLoopRestDurationSeconds,
                            missionBattleWaitBaseSeconds = missionBaseWait.toIntOrNull() ?: current.missionBattleWaitBaseSeconds,
                            missionBattleWaitRandomSeconds = missionRandomWait.toIntOrNull() ?: current.missionBattleWaitRandomSeconds,
                            eventBattleWaitBaseSeconds = eventBaseWait.toIntOrNull() ?: current.eventBattleWaitBaseSeconds,
                            eventBattleWaitRandomSeconds = eventRandomWait.toIntOrNull() ?: current.eventBattleWaitRandomSeconds,
                            eudemonBattleWaitBaseSeconds = eudemonBaseWait.toIntOrNull() ?: current.eudemonBattleWaitBaseSeconds,
                            eudemonBattleWaitRandomSeconds = eudemonRandomWait.toIntOrNull() ?: current.eudemonBattleWaitRandomSeconds,
                            eudemonBetweenBattlesDelaySeconds = eudemonBetweenDelay.toIntOrNull() ?: current.eudemonBetweenBattlesDelaySeconds,
                            huntingHouseBattleWaitBaseSeconds = huntingBaseWait.toIntOrNull() ?: current.huntingHouseBattleWaitBaseSeconds,
                            huntingHouseBattleWaitRandomSeconds = huntingRandomWait.toIntOrNull() ?: current.huntingHouseBattleWaitRandomSeconds,
                            huntingHouseBetweenBattlesDelaySeconds = huntingBetweenDelay.toIntOrNull() ?: current.huntingHouseBetweenBattlesDelaySeconds,
                            examWaitMinSeconds = examMinWait.toIntOrNull() ?: current.examWaitMinSeconds,
                            examWaitMaxSeconds = examMaxWait.toIntOrNull() ?: current.examWaitMaxSeconds,
                            examStageGapSeconds = examStageGap.toIntOrNull() ?: current.examStageGapSeconds,
                            specialJouninClassSkill = specialJouninSkill.ifBlank { current.specialJouninClassSkill },
                            eventResourceMode = eventResourceMode.ifBlank { current.eventResourceMode },
                            eventWaitMinutes = eventWaitMinutes.toIntOrNull() ?: current.eventWaitMinutes,
                            easterEventResourceMode = easterEventResourceMode.ifBlank { current.easterEventResourceMode },
                            easterEventWaitMinutes = easterEventWaitMinutes.toIntOrNull() ?: current.easterEventWaitMinutes,
                        )
                    )
                },
            ) { Text("Save") }
        },
        dismissButton = {
            OutlinedButton(onClick = onDismiss) { Text("Cancel") }
        },
        containerColor = Color(0xFF15110F),
    )
}

@Composable
private fun CategoryButtonCard(
    title: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    ElevatedCard(
        modifier = modifier,
        colors = CardDefaults.elevatedCardColors(containerColor = Color(0xFF181C1E)),
        onClick = onClick,
    ) {
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .defaultMinSize(minHeight = 92.dp)
                .padding(14.dp),
            contentAlignment = Alignment.Center,
        ) {
            Text(
                text = title,
                color = Color(0xFFEDE2D1),
                style = MaterialTheme.typography.titleMedium,
            )
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun ActionButtonCard(
    action: ActionUi,
    uiState: UiState,
    viewModel: AppViewModel,
    modifier: Modifier = Modifier,
) {
    val isNinjaSagaClanWar = uiState.currentBaseGame?.id == "ninjasaga" && action.key == "clan_war"
    ElevatedCard(
        modifier = modifier,
        colors = CardDefaults.elevatedCardColors(containerColor = Color(0xFF181C1E)),
    ) {
        Column(
            modifier = Modifier.padding(12.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Text(action.label, color = Color(0xFFEDE2D1), style = MaterialTheme.typography.titleSmall)
            if (action.enemyOptions.isNotEmpty()) {
                var expanded by remember(action.key) { mutableStateOf(false) }
                val selectedId = uiState.selectedEnemies[action.key] ?: action.enemyOptions.first().id
                val selectedLabel = action.enemyOptions.firstOrNull { it.id == selectedId }?.name ?: selectedId
                val selectorLabel = if (action.key == "minigame_event") "Minigame" else "Enemy"

                ExposedDropdownMenuBox(
                    expanded = expanded,
                    onExpandedChange = { expanded = !expanded },
                ) {
                    OutlinedTextField(
                        value = selectedLabel,
                        onValueChange = {},
                        readOnly = true,
                        modifier = Modifier
                            .menuAnchor()
                            .fillMaxWidth(),
                        label = { Text(selectorLabel) },
                        trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = expanded) },
                        singleLine = true,
                    )
                    DropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
                        action.enemyOptions.forEach { option ->
                            DropdownMenuItem(
                                text = { Text(option.name) },
                                onClick = {
                                    viewModel.chooseEnemy(action.key, option.id)
                                    expanded = false
                                },
                            )
                        }
                    }
                }
            }
            Button(
                onClick = {
                    if (isNinjaSagaClanWar) {
                        viewModel.openClanWarPanel()
                    } else {
                        viewModel.startAction(action)
                    }
                },
                enabled = if (isNinjaSagaClanWar) {
                    uiState.hasBillingAccess && !uiState.actionStateSyncing
                } else {
                    !uiState.running && !uiState.actionStateSyncing && uiState.hasBillingAccess
                },
                modifier = Modifier
                    .fillMaxWidth()
                    .defaultMinSize(minHeight = 42.dp),
                contentPadding = PaddingValues(horizontal = 12.dp, vertical = 8.dp),
            ) {
                Text(
                    if (!uiState.hasBillingAccess) {
                        "Locked"
                    } else if (uiState.actionStateSyncing) {
                        "Syncing..."
                    } else if (isNinjaSagaClanWar) {
                        "Open Panel"
                    } else {
                        "Start"
                    },
                    style = MaterialTheme.typography.labelLarge,
                )
            }
        }
    }
}

@Composable
private fun NinjaSagaClanWarPanelOverlay(
    uiState: UiState,
    viewModel: AppViewModel,
) {
    val panel = uiState.clanWarPanel
    val current = uiState.ninjaSagaSettings
    var settingsVisible by rememberSaveable { mutableStateOf(false) }
    var warListVisible by rememberSaveable { mutableStateOf(false) }
    var membersVisible by rememberSaveable { mutableStateOf(false) }
    var showWarListPicker by rememberSaveable { mutableStateOf(false) }
    var showMemberPicker by rememberSaveable { mutableStateOf(false) }
    var pendingTargetClanId by rememberSaveable { mutableStateOf("") }
    var pendingTargetClanName by rememberSaveable { mutableStateOf("") }
    var selectedWarTargetId by rememberSaveable(panel.warList.map { it.id }.joinToString("|")) {
        mutableStateOf(
            panel.currentTargetId.takeIf { it.isNotBlank() }
                ?: panel.warList.firstOrNull()?.id.orEmpty()
        )
    }
    var selectedRecruitIds by rememberSaveable(panel.memberList.map { it.id }.joinToString("|")) {
        mutableStateOf(
            panel.selectedRecruiters.take(2)
                .filter { savedId -> panel.memberList.any { it.id == savedId } }
        )
    }
    var clanWarAutoSpendToken by rememberSaveable(panel.showing, current.clanWarAutoSpendToken) { mutableStateOf(current.clanWarAutoSpendToken) }
    var clanWarStaminaRefillSource by rememberSaveable(panel.showing, current.clanWarStaminaRefillSource) { mutableStateOf(current.clanWarStaminaRefillSource.ifBlank { "auto" }) }
    var clanWarBleedingMode by rememberSaveable(panel.showing, current.clanWarBleedingMode) { mutableStateOf(current.clanWarBleedingMode) }
    var clanWarManualRecruit by rememberSaveable(panel.showing, current.clanWarManualRecruit) { mutableStateOf(current.clanWarManualRecruit) }
    var clanWarBattleDelay by rememberSaveable(panel.showing, current.clanWarBattleDelaySeconds) { mutableStateOf(current.clanWarBattleDelaySeconds.toString()) }
    var clanWarRefreshDelay by rememberSaveable(panel.showing, current.clanWarRefreshDelaySeconds) { mutableStateOf(current.clanWarRefreshDelaySeconds.toString()) }
    var clanWarBuyStaminaDelay by rememberSaveable(panel.showing, current.clanWarBuyStaminaDelaySeconds) { mutableStateOf(current.clanWarBuyStaminaDelaySeconds.toString()) }
    var clanWarAmfCallDelay by rememberSaveable(panel.showing, current.clanWarAmfCallDelaySeconds) { mutableStateOf(current.clanWarAmfCallDelaySeconds.toString()) }
    var clanWarPostCaptchaDelay by rememberSaveable(panel.showing, current.clanWarPostCaptchaResumeDelaySeconds) { mutableStateOf(current.clanWarPostCaptchaResumeDelaySeconds.toString()) }
    var clanWarLowStaminaWait by rememberSaveable(panel.showing, current.clanWarLowStaminaWaitMinutes) { mutableStateOf(current.clanWarLowStaminaWaitMinutes.toString()) }
    var selectedHelpKey by rememberSaveable { mutableStateOf<String?>(null) }

    fun buildUpdatedSettings(): NinjaSagaSettingsUi {
        return current.copy(
            clanWarAutoSpendToken = clanWarAutoSpendToken,
            clanWarStaminaRefillSource = clanWarStaminaRefillSource.ifBlank { "auto" },
            clanWarBleedingMode = clanWarBleedingMode,
            clanWarManualRecruit = clanWarManualRecruit,
            clanWarManualMemberIds = current.clanWarManualMemberIds,
            clanWarTargetClanId = current.clanWarTargetClanId,
            clanWarTargetClanName = current.clanWarTargetClanName,
            clanWarBattleDelaySeconds = clanWarBattleDelay.toIntOrNull() ?: current.clanWarBattleDelaySeconds,
            clanWarRefreshDelaySeconds = clanWarRefreshDelay.toIntOrNull() ?: current.clanWarRefreshDelaySeconds,
            clanWarBuyStaminaDelaySeconds = clanWarBuyStaminaDelay.toIntOrNull() ?: current.clanWarBuyStaminaDelaySeconds,
            clanWarAmfCallDelaySeconds = clanWarAmfCallDelay.toIntOrNull() ?: current.clanWarAmfCallDelaySeconds,
            clanWarPostCaptchaResumeDelaySeconds = clanWarPostCaptchaDelay.toIntOrNull() ?: current.clanWarPostCaptchaResumeDelaySeconds,
            clanWarLowStaminaWaitMinutes = clanWarLowStaminaWait.toIntOrNull() ?: current.clanWarLowStaminaWaitMinutes,
        )
    }

    Card(
        modifier = Modifier
            .fillMaxSize()
            .padding(12.dp),
        colors = CardDefaults.cardColors(containerColor = Color(0xFF111111)),
    ) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(12.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Column(modifier = Modifier.weight(1f)) {
                    Text("NinjaSaga Clan War", color = Color.White, style = MaterialTheme.typography.titleLarge)
                    Text(
                        panel.error ?: uiState.statusMessage.orEmpty(),
                        color = if (panel.error.isNullOrBlank()) Color(0xFFE0D0B8) else Color(0xFFFF8A80),
                        style = MaterialTheme.typography.bodySmall,
                    )
                }
                OutlinedButton(onClick = viewModel::closeClanWarPanel) {
                    Text("Close")
                }
            }

            ElevatedCard(colors = CardDefaults.elevatedCardColors(containerColor = Color(0xFF181818))) {
                Column(modifier = Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    Text("Clan Info", color = Color(0xFFFFC978), style = MaterialTheme.typography.titleSmall)
                    Text("Clan: ${panel.clan.name}", color = Color.White)
                    Text("Clan ID: ${panel.clan.id.ifBlank { "-" }}", color = Color(0xFFE0D0B8))
                    Text("Reputation: ${panel.clan.reputation}", color = Color(0xFFC6DE94))
                    Text("Stamina: ${panel.character.stamina}/${panel.character.maxStamina}", color = Color(0xFFC6DE94))
                    Text("Prestige: ${panel.character.prestige}", color = Color(0xFFE0D0B8))
                    if (panel.selectedRecruiters.isNotEmpty()) {
                        Text("Recruiters: ${panel.selectedRecruiters.joinToString(", ")}", color = Color(0xFFE0D0B8))
                    }
                }
            }

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                OutlinedButton(
                    onClick = { viewModel.applyClanWarPanelSettings(buildUpdatedSettings(), refreshAfterSave = true) },
                    enabled = !panel.loading,
                    modifier = Modifier.weight(1f),
                ) {
                    Text(if (panel.loading) "Loading..." else "Refresh")
                }
                Button(
                    onClick = {
                        if (panel.warList.isEmpty()) {
                            viewModel.refreshClanWarPanel()
                        } else {
                            showWarListPicker = true
                        }
                    },
                    enabled = !uiState.running && !panel.loading,
                    modifier = Modifier.weight(1f),
                ) {
                    Text(if (panel.running) "Running" else "Battle")
                }
                OutlinedButton(
                    onClick = viewModel::stopAction,
                    enabled = uiState.running,
                    modifier = Modifier.weight(1f),
                ) {
                    Text("Stop")
                }
            }

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                OutlinedButton(onClick = { warListVisible = !warListVisible }, modifier = Modifier.weight(1f)) {
                    Text(if (warListVisible) "Hide War List" else "Show War List")
                }
                OutlinedButton(onClick = { settingsVisible = !settingsVisible }, modifier = Modifier.weight(1f)) {
                    Text(if (settingsVisible) "Hide Settings" else "Show Settings")
                }
                OutlinedButton(onClick = { membersVisible = !membersVisible }, modifier = Modifier.weight(1f)) {
                    Text(if (membersVisible) "Hide Members" else "Show Members")
                }
            }

            if (settingsVisible) {
                ElevatedCard(colors = CardDefaults.elevatedCardColors(containerColor = Color(0xFF17130F))) {
                    Column(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(12.dp)
                            .verticalScroll(rememberScrollState()),
                        verticalArrangement = Arrangement.spacedBy(8.dp),
                    ) {
                        Text("Settings", color = Color(0xFFFFC978), style = MaterialTheme.typography.titleSmall)
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Checkbox(checked = clanWarAutoSpendToken, onCheckedChange = { clanWarAutoSpendToken = it })
                            Text("Auto Refill Stamina", color = Color.White)
                        }
                        Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            OutlinedButton(onClick = { clanWarStaminaRefillSource = "auto" }, modifier = Modifier.weight(1f)) {
                                Text(if (clanWarStaminaRefillSource == "auto") "Auto *" else "Auto")
                            }
                            OutlinedButton(onClick = { clanWarStaminaRefillSource = "token" }, modifier = Modifier.weight(1f)) {
                                Text(if (clanWarStaminaRefillSource == "token") "Token *" else "Token")
                            }
                            OutlinedButton(onClick = { clanWarStaminaRefillSource = "roll" }, modifier = Modifier.weight(1f)) {
                                Text(if (clanWarStaminaRefillSource == "roll") "Onigiri *" else "Onigiri")
                            }
                        }
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Checkbox(checked = clanWarBleedingMode, onCheckedChange = { clanWarBleedingMode = it })
                            Text("Bleeding Mode", color = Color.White)
                        }
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Checkbox(checked = clanWarManualRecruit, onCheckedChange = { clanWarManualRecruit = it })
                            Text("Manual Recruit", color = Color.White)
                        }
                        ClanWarDelayField("Battle Delay (s)", "battle_delay", selectedHelpKey, { selectedHelpKey = if (selectedHelpKey == it) null else it }, clanWarBattleDelay) { clanWarBattleDelay = it }
                        ClanWarDelayField("Refresh Delay (s)", "refresh_delay", selectedHelpKey, { selectedHelpKey = if (selectedHelpKey == it) null else it }, clanWarRefreshDelay) { clanWarRefreshDelay = it }
                        ClanWarDelayField("Buy Stamina Delay (s)", "buy_delay", selectedHelpKey, { selectedHelpKey = if (selectedHelpKey == it) null else it }, clanWarBuyStaminaDelay) { clanWarBuyStaminaDelay = it }
                        ClanWarDelayField("AMF Call Delay (s)", "amf_delay", selectedHelpKey, { selectedHelpKey = if (selectedHelpKey == it) null else it }, clanWarAmfCallDelay) { clanWarAmfCallDelay = it }
                        ClanWarDelayField("Post Captcha Delay (s)", "captcha_delay", selectedHelpKey, { selectedHelpKey = if (selectedHelpKey == it) null else it }, clanWarPostCaptchaDelay) { clanWarPostCaptchaDelay = it }
                        ClanWarDelayField("Low Stamina Wait (min, 0=stop)", "low_stamina_wait", selectedHelpKey, { selectedHelpKey = if (selectedHelpKey == it) null else it }, clanWarLowStaminaWait) { clanWarLowStaminaWait = it }
                        OutlinedButton(
                            onClick = { viewModel.applyClanWarPanelSettings(buildUpdatedSettings(), refreshAfterSave = true) },
                            modifier = Modifier.fillMaxWidth(),
                        ) {
                            Text("Save Settings")
                        }
                    }
                }
            }

            ElevatedCard(
                colors = CardDefaults.elevatedCardColors(containerColor = Color(0xFF181818)),
                modifier = Modifier.weight(1f),
            ) {
                Column(
                    modifier = Modifier
                        .fillMaxSize()
                        .padding(12.dp)
                        .verticalScroll(rememberScrollState()),
                    verticalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    if (warListVisible) {
                        Text("War List", color = Color(0xFFFFC978), style = MaterialTheme.typography.titleSmall)
                        if (panel.warList.isEmpty()) {
                            Text("No clan war targets loaded.", color = Color(0xFFE0D0B8))
                        } else {
                            panel.warList.forEach { item ->
                                ElevatedCard(colors = CardDefaults.elevatedCardColors(containerColor = Color(0xFF222222))) {
                                    Column(modifier = Modifier.padding(10.dp), verticalArrangement = Arrangement.spacedBy(3.dp)) {
                                        Text(item.name, color = Color.White)
                                        Text("ID: ${item.id.ifBlank { "-" }}", color = Color(0xFFE0D0B8))
                                        Text("REP: ${item.reputation} | Master: ${item.master}", color = Color(0xFFC6DE94))
                                        Text("Members: ${item.members}", color = Color(0xFFE0D0B8))
                                    }
                                }
                            }
                        }
                    }

                    if (membersVisible) {
                        Text("Members", color = Color(0xFFFFC978), style = MaterialTheme.typography.titleSmall)
                        if (panel.memberList.isEmpty()) {
                            Text("No member list loaded.", color = Color(0xFFE0D0B8))
                        } else {
                            panel.memberList.forEach { member ->
                                ElevatedCard(colors = CardDefaults.elevatedCardColors(containerColor = Color(0xFF222222))) {
                                    Column(modifier = Modifier.padding(10.dp), verticalArrangement = Arrangement.spacedBy(3.dp)) {
                                        Text("${member.name} (Lv ${member.level})", color = Color.White)
                                        Text("ID: ${member.id.ifBlank { "-" }}", color = Color(0xFFE0D0B8))
                                        Text("Stamina: ${member.stamina} | REP Gain: ${member.reputationGain}", color = Color(0xFFC6DE94))
                                    }
                                }
                            }
                        }
                    }

                }
            }
        }
    }

    if (showWarListPicker) {
        AlertDialog(
            onDismissRequest = { showWarListPicker = false },
            title = { Text("Choose Target Clan", color = Color.White) },
            text = {
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .heightIn(max = 420.dp)
                        .verticalScroll(rememberScrollState()),
                    verticalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    if (panel.warList.isEmpty()) {
                        Text("No clan war target available right now.", color = Color(0xFFE0D0B8))
                    } else {
                        panel.warList.forEach { item ->
                            val isSelected = item.id == selectedWarTargetId
                            OutlinedButton(
                                onClick = { selectedWarTargetId = item.id },
                                modifier = Modifier.fillMaxWidth(),
                                colors = ButtonDefaults.outlinedButtonColors(
                                    containerColor = if (isSelected) Color(0xFF3A2610) else Color.Transparent,
                                    contentColor = if (isSelected) Color(0xFFFFC978) else Color.White,
                                ),
                            ) {
                                Column(modifier = Modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(2.dp)) {
                                    Text(item.name)
                                    Text("ID: ${item.id}", color = Color(0xFFE0D0B8), style = MaterialTheme.typography.bodySmall)
                                    Text("REP: ${item.reputation} | Members: ${item.members}", color = Color(0xFFC6DE94), style = MaterialTheme.typography.bodySmall)
                                }
                            }
                        }
                    }
                }
            },
            confirmButton = {
                Button(
                    onClick = {
                        val selectedClan = panel.warList.firstOrNull { it.id == selectedWarTargetId }
                        if (selectedClan != null) {
                            pendingTargetClanId = selectedClan.id
                            pendingTargetClanName = selectedClan.name
                            showWarListPicker = false
                            if (clanWarManualRecruit) {
                                selectedRecruitIds = panel.selectedRecruiters.take(2).filter { savedId -> panel.memberList.any { it.id == savedId } }
                                showMemberPicker = true
                            } else {
                                viewModel.startClanWarFromSelection(selectedClan.id, selectedClan.name, emptyList())
                            }
                        }
                    },
                    enabled = selectedWarTargetId.isNotBlank() && panel.warList.isNotEmpty(),
                ) {
                    Text(if (clanWarManualRecruit) "Next" else "Battle")
                }
            },
            dismissButton = {
                OutlinedButton(onClick = { showWarListPicker = false }) {
                    Text("Cancel")
                }
            },
            containerColor = Color(0xFF15110F),
        )
    }

    if (showMemberPicker) {
        AlertDialog(
            onDismissRequest = { showMemberPicker = false },
            title = { Text("Choose Recruiters", color = Color.White) },
            text = {
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .heightIn(max = 420.dp)
                        .verticalScroll(rememberScrollState()),
                    verticalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    if (panel.memberList.isEmpty()) {
                        Text("No member list loaded.", color = Color(0xFFE0D0B8))
                    } else {
                        panel.memberList.sortedByDescending { it.stamina }.forEach { member ->
                            val selected = selectedRecruitIds.contains(member.id)
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                verticalAlignment = Alignment.CenterVertically,
                                horizontalArrangement = Arrangement.spacedBy(8.dp),
                            ) {
                                Checkbox(
                                    checked = selected,
                                    onCheckedChange = { checked ->
                                        selectedRecruitIds = if (checked) {
                                            (selectedRecruitIds + member.id).distinct().take(2)
                                        } else {
                                            selectedRecruitIds.filterNot { it == member.id }
                                        }
                                    },
                                )
                                Column(modifier = Modifier.weight(1f)) {
                                    Text("${member.name} (Lv ${member.level})", color = Color.White)
                                    Text("Stamina ${member.stamina} | REP Gain ${member.reputationGain}", color = Color(0xFFC6DE94), style = MaterialTheme.typography.bodySmall)
                                    Text("ID: ${member.id}", color = Color(0xFFE0D0B8), style = MaterialTheme.typography.bodySmall)
                                }
                            }
                        }
                    }
                }
            },
            confirmButton = {
                Button(
                    onClick = {
                        showMemberPicker = false
                        viewModel.startClanWarFromSelection(pendingTargetClanId, pendingTargetClanName, selectedRecruitIds)
                    },
                    enabled = pendingTargetClanId.isNotBlank() && selectedRecruitIds.isNotEmpty(),
                ) {
                    Text("Battle")
                }
            },
            dismissButton = {
                OutlinedButton(onClick = { showMemberPicker = false }) {
                    Text("Cancel")
                }
            },
            containerColor = Color(0xFF15110F),
        )
    }
}

@Composable
private fun ClanWarDelayField(
    label: String,
    helpKey: String,
    selectedHelpKey: String?,
    onToggleHelp: (String) -> Unit,
    value: String,
    onValueChange: (String) -> Unit,
) {
    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(label, color = Color(0xFFEDE2D1))
            TextButton(onClick = { onToggleHelp(helpKey) }, contentPadding = PaddingValues(horizontal = 6.dp, vertical = 0.dp)) {
                Text("?", color = Color(0xFFFFC978))
            }
        }
        OutlinedTextField(
            value = value,
            onValueChange = onValueChange,
            singleLine = true,
            modifier = Modifier.fillMaxWidth(),
        )
        if (selectedHelpKey == helpKey) {
            Text(
                text = clanWarHelpText(helpKey),
                color = Color(0xFFB8A98E),
                style = MaterialTheme.typography.bodySmall,
            )
        }
    }
}

private fun clanWarHelpText(key: String): String {
    return when (key) {
        "battle_delay" -> "Delay between one Clan War battle and the next battle request."
        "refresh_delay" -> "Delay before trying again when no target clan is available."
        "buy_delay" -> "Delay after buying stamina before the next Clan War step."
        "amf_delay" -> "Extra delay before each Clan War AMF call."
        "captcha_delay" -> "Delay after captcha success before the resumed Clan War flow continues."
        else -> ""
    }
}

@Composable
private fun AdStackCard() {
    Unit
}

@Composable
private fun BillingExpiredOverlay(
    runningAction: String?,
    onAddTimeClick: () -> Unit,
    rewardedButtonLabel: String,
    rewardedButtonEnabled: Boolean,
    showAds: Boolean,
) {
    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(Color(0xC0101010)),
        contentAlignment = Alignment.Center,
    ) {
        ElevatedCard(colors = CardDefaults.elevatedCardColors(containerColor = Color(0xFF18120F))) {
            Column(
                modifier = Modifier.padding(20.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp),
                horizontalAlignment = Alignment.CenterHorizontally,
            ) {
                Text("Billing Expired", style = MaterialTheme.typography.headlineSmall, color = Color.White)
                Text(
                    "Automation actions are locked until you add more billing time.",
                    color = Color(0xFFE0D0B8),
                )
                if (!runningAction.isNullOrBlank()) {
                    Text(
                        "Stopped action: $runningAction",
                        color = Color(0xFFFFCC80),
                    )
                }
                if (!BuildConfig.DISABLE_ADS && showAds) {
                    Button(
                        onClick = onAddTimeClick,
                        enabled = rewardedButtonEnabled,
                    ) {
                        Text(rewardedButtonLabel)
                    }
                }
            }
        }
    }
}

@Composable
private fun LogPanel(uiState: UiState, viewModel: AppViewModel) {
    val visibleLogs = uiState.logs.take(120)
    val logListState = rememberLazyListState()

    LaunchedEffect(visibleLogs.size) {
        if (visibleLogs.isNotEmpty()) {
            logListState.scrollToItem(visibleLogs.lastIndex)
        }
    }

    ElevatedCard(colors = CardDefaults.elevatedCardColors(containerColor = Color(0xFF0E0E0E))) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text("Logs", style = MaterialTheme.typography.headlineSmall, color = Color.White)
                OutlinedButton(onClick = viewModel::clearLogs) {
                    Text("Clear")
                }
            }
            if (uiState.logs.isEmpty()) {
                Text("No logs yet.", color = Color(0xFF8B8B8B))
            } else {
                LazyColumn(
                    state = logListState,
                    modifier = Modifier
                        .fillMaxWidth()
                        .heightIn(max = 280.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    items(visibleLogs.size) { index ->
                        val log = visibleLogs[index]
                        Text(
                            text = log.message,
                            color = when (log.level) {
                                "error" -> Color(0xFFFF8A80)
                                "success" -> Color(0xFFA5D6A7)
                                "warning" -> Color(0xFFFFCC80)
                                else -> Color(0xFFE0E0E0)
                            },
                        )
                    }
                }
            }
        }
    }
}

private fun formatBillingRemaining(millis: Long): String {
    if (BuildConfig.INFINITE_BILLING) return "\u221E"
    if (millis <= 0L) return "Expired"
    val totalMinutes = TimeUnit.MILLISECONDS.toMinutes(millis)
    val hours = totalMinutes / 60
    val minutes = totalMinutes % 60
    return String.format("%02dh %02dm", hours, minutes)
}

private fun buildBillingHeaderDetail(uiState: UiState): String {
    val username = uiState.billingUsername.orEmpty()
    return "$username - ${formatBillingDateTime(uiState.billingExpiryMillis)} Expired"
}

private fun formatBillingDateTime(millis: Long): String {
    if (BuildConfig.INFINITE_BILLING || millis == Long.MAX_VALUE) return "Never"
    if (millis <= 0L) return "Expired"
    return SimpleDateFormat("yyyy-MM-dd HH:mm", Locale.US).format(Date(millis))
}

