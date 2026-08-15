package com.ninjasage.android

import android.content.Context
import android.content.pm.ApplicationInfo
import android.os.Build

object SecurityUtils {
    fun isRunningOnLikelyUnsafeDevice(context: Context): Boolean {
        val tags = Build.TAGS ?: ""
        val rootHints = listOf(
            "/system/xbin/su",
            "/system/bin/su",
            "/system/app/Superuser.apk",
            "/sbin/su",
        )
        val rooted = tags.contains("test-keys") || rootHints.any { java.io.File(it).exists() }
        val debuggable = (context.applicationInfo.flags and ApplicationInfo.FLAG_DEBUGGABLE) != 0
        return rooted || debuggable
    }
}
