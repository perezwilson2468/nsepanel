package com.ninjasage.android

import android.content.Context

/**
 * Stub billing repository. Since this is the open-source build with INFINITE_BILLING = true,
 * all billing checks always return full access with no expiry.
 */
class BillingTimeRepository(context: Context) {

    private val infiniteSnapshot = BillingSnapshot(
        remainingMillis = Long.MAX_VALUE,
        expiryMillis = Long.MAX_VALUE,
        hasAccess = true,
        username = "TheForgotten",
        subscriptionActive = true,
        disableAds = true,
    )

    fun snapshotNow(): BillingSnapshot = infiniteSnapshot

    fun refresh(): BillingSnapshot = infiniteSnapshot

    fun grantRewardHours(hours: Int): BillingSnapshot = infiniteSnapshot
}