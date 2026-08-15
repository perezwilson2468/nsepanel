package com.ninjasage.android

import android.content.Context
import android.content.SharedPreferences
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey
import org.json.JSONObject

class SecureCredentialsStore(context: Context) {
    private val appContext = context.applicationContext
    private val fallbackPrefs: SharedPreferences by lazy {
        appContext.getSharedPreferences("login_store_fallback", Context.MODE_PRIVATE)
    }

    private val prefs: SharedPreferences by lazy {
        try {
            val masterKey = MasterKey.Builder(appContext)
                .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
                .build()

            EncryptedSharedPreferences.create(
                appContext,
                "secure_login_store",
                masterKey,
                EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
                EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM,
            )
        } catch (_: Throwable) {
            fallbackPrefs
        }
    }

    fun save(profileId: String, username: String, password: String) {
        if (profileId.isBlank()) return
        val store = loadStore()
        store.getJSONObject("profiles").put(
            profileId,
            JSONObject()
                .put("username", username)
                .put("password", password),
        )
        store.put("last_profile_id", profileId)
        prefs.edit().putString("quick_login_profiles", store.toString()).apply()
    }

    fun load(profileId: String): Pair<String, String>? {
        if (profileId.isBlank()) return null
        val profile = loadStore().optJSONObject("profiles")?.optJSONObject(profileId)
        val username = profile?.optString("username")
        val password = profile?.optString("password")
        return if (!username.isNullOrBlank() && !password.isNullOrBlank()) {
            username to password
        } else {
            null
        }
    }

    fun hasSavedLogin(profileId: String): Boolean = load(profileId) != null

    fun clear() {
        prefs.edit().clear().apply()
    }

    private fun loadStore(): JSONObject {
        val raw = prefs.getString("quick_login_profiles", null)
        return try {
            val store = if (raw.isNullOrBlank()) JSONObject() else JSONObject(raw)
            if (!store.has("profiles") || store.optJSONObject("profiles") == null) {
                store.put("profiles", JSONObject())
            }
            store
        } catch (_: Throwable) {
            JSONObject().put("profiles", JSONObject())
        }
    }
}
