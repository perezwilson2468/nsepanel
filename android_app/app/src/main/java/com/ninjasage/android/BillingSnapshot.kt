package com.ninjasage.android

data class BillingSnapshot(
    val remainingMillis: Long = Long.MAX_VALUE,
    val expiryMillis: Long = Long.MAX_VALUE,
    val hasAccess: Boolean = true,
    val username: String? = null,
    val subscriptionActive: Boolean = true,
    val disableAds: Boolean = true,
)