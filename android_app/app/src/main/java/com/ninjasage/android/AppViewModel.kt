package com.ninjasage.android

import android.app.Application
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.VibrationEffect
import android.os.Vibrator
import android.os.VibratorManager
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.core.content.ContextCompat
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import com.theforgotten.nsepanel.R
import org.json.JSONArray
import org.json.JSONObject

data class CharacterSummary(
    val name: String,
    val level: Int,
    val xp: Int,
    val gold: Int,
    val tokens: Int,
    val characterId: String,
)

data class CharacterOption(
    val index: Int,
    val id: String,
    val name: String,
    val level: Int,
)

data class LogEntry(
    val message: String,
    val level: String,
)

data class EnemyOption(
    val id: String,
    val name: String,
)

data class AmfProfileOption(
    val id: String,
    val label: String,
    val gateway: String,
    val buildNum: String,
)

data class BaseGameOption(
    val id: String,
    val label: String,
    val serverSelectionNote: String,
)

data class NinjaSagaSettingsUi(
    val levelingActionDelaySeconds: Int = 10,
    val levelingCycleCooldownSeconds: Int = 5,
    val levelingRestEveryCycles: Int = 40,
    val levelingRestDurationSeconds: Int = 60,
    val levelingActionJitterSeconds: Int = 2,
    val levelingMinCallDelaySeconds: Int = 4,
    val levelingStartRetryDelaySeconds: Int = 6,
    val levelingStartMaxRetries: Int = 3,
    val levelingCloudflareRestSeconds: Int = 60,
    val levelingCloudflareBackoffSteps: String = "60,120,240",
    val levelingFailureWindowSeconds: Int = 180,
    val levelingMaxFailuresInWindow: Int = 6,
    val levelingCircuitCooldownSeconds: Int = 120,
    val eudemonStartFinishDelaySeconds: Int = 25,
    val eudemonCycleCooldownSeconds: Int = 5,
    val easterBattleDelaySeconds: Int = 25,
    val easterCycleCooldownSeconds: Int = 5,
    val sakuraBattleDelaySeconds: Int = 20,
    val easterAutoSpendEnabled: Boolean = false,
    val easterAutoSpendMaxRefillsPerRun: Int = 0,
    val easterAutoSpendBuyAmount: Int = 3,
    val eventResourceMode: String = "stop",
    val eventWaitMinutes: Int = 30,
    val specialJouninClassIndex: Int = 1,
    val tpTrainingAbuseLoop: Int = 1,
    val ssTrainingAbuseLoop: Int = 1,
    val clanWarAutoSpendToken: Boolean = false,
    val clanWarStaminaRefillSource: String = "auto",
    val clanWarBleedingMode: Boolean = false,
    val clanWarManualRecruit: Boolean = false,
    val clanWarManualMemberIds: String = "",
    val clanWarTargetClanId: String = "",
    val clanWarTargetClanName: String = "",
    val clanWarBattleDelaySeconds: Int = 8,
    val clanWarRefreshDelaySeconds: Int = 4,
    val clanWarBuyStaminaDelaySeconds: Int = 3,
    val clanWarAmfCallDelaySeconds: Int = 1,
    val clanWarPostCaptchaResumeDelaySeconds: Int = 4,
    val clanWarLowStaminaWaitMinutes: Int = 30,
)

data class SageSettingsUi(
    val generalActionDelaySeconds: Int = 10,
    val cycleCooldownSeconds: Int = 5,
    val restEveryCycles: Int = 40,
    val restDurationSeconds: Int = 60,
    val actionJitterSeconds: Int = 2,
    val minCallDelaySeconds: Int = 4,
    val startRetryDelaySeconds: Int = 6,
    val startMaxRetries: Int = 3,
    val failureWindowSeconds: Int = 180,
    val maxFailuresInWindow: Int = 6,
    val circuitCooldownSeconds: Int = 120,
    val examStartDelaySeconds: Int = 8,
    val examFinishDelaySeconds: Int = 5,
    val battleDurationDelaySeconds: Int = 5,
    val afterFinishDelaySeconds: Int = 0,
    val autoReloginWaitSeconds: Int = 20,
    val infiniteLoopRestEveryMissions: Int = 50,
    val infiniteLoopRestDurationSeconds: Int = 10,
    val limitedLoopRestEveryMissions: Int = 15,
    val limitedLoopRestDurationSeconds: Int = 10,
    val specialJouninClassSkill: String = "skill_4001",
    val eventResourceMode: String = "stop",
    val eventWaitMinutes: Int = 30,
    val anivEventResourceMode: String = "stop",
    val anivEventWaitMinutes: Int = 30,
    val sakuraEventResourceMode: String = "stop",
    val sakuraEventWaitMinutes: Int = 30,
    val easterEventResourceMode: String = "stop",
    val easterEventWaitMinutes: Int = 30,
    val shadowWarResourceMode: String = "stop",
    val shadowWarWaitMinutes: Int = 30,
    val clanWarAutoSpendToken: Boolean = false,
    val clanWarStaminaRefillSource: String = "auto",
    val clanWarBattleDelaySeconds: Int = 8,
    val clanWarBuyStaminaDelaySeconds: Int = 3,
)

data class RiftSkillOption(
    val id: String,
    val label: String,
)

data class RiftSettingsUi(
    val minCallDelaySeconds: Int = 2,
    val loopDelaySeconds: Int = 1,
    val autoReloginWaitSeconds: Int = 15,
    val infiniteLoopRestEveryCycles: Int = 40,
    val infiniteLoopRestDurationSeconds: Int = 30,
    val limitedLoopRestEveryCycles: Int = 15,
    val limitedLoopRestDurationSeconds: Int = 15,
    val missionBattleWaitBaseSeconds: Int = 20,
    val missionBattleWaitRandomSeconds: Int = 20,
    val eventBattleWaitBaseSeconds: Int = 20,
    val eventBattleWaitRandomSeconds: Int = 20,
    val eudemonBattleWaitBaseSeconds: Int = 20,
    val eudemonBattleWaitRandomSeconds: Int = 5,
    val eudemonBetweenBattlesDelaySeconds: Int = 5,
    val huntingHouseBattleWaitBaseSeconds: Int = 20,
    val huntingHouseBattleWaitRandomSeconds: Int = 5,
    val huntingHouseBetweenBattlesDelaySeconds: Int = 5,
    val examWaitMinSeconds: Int = 45,
    val examWaitMaxSeconds: Int = 120,
    val examStageGapSeconds: Int = 3,
    val specialJouninClassSkill: String = "skill_2001",
    val eventResourceMode: String = "stop",
    val eventWaitMinutes: Int = 30,
    val hanamiEventResourceMode: String = "stop",
    val hanamiEventWaitMinutes: Int = 30,
    val easterEventResourceMode: String = "stop",
    val easterEventWaitMinutes: Int = 30,
)

data class ActionUi(
    val key: String,
    val label: String,
    val enemyOptions: List<EnemyOption>,
)

data class ClanWarCaptchaUi(
    val required: Boolean = false,
    val message: String = "",
    val challengeJson: String? = null,
    val loading: Boolean = false,
    val verifying: Boolean = false,
    val error: String? = null,
    val debugJson: String? = null,
    val submittedAnswer: String? = null,
)

data class ClanWarClanInfoUi(
    val id: String = "",
    val name: String = "Unknown Clan",
    val reputation: Int = 0,
)

data class ClanWarCharacterInfoUi(
    val stamina: Int = 0,
    val maxStamina: Int = 0,
    val prestige: String = "n/a",
)

data class ClanWarWarItemUi(
    val id: String,
    val name: String,
    val reputation: String,
    val master: String,
    val members: String,
)

data class ClanWarMemberUi(
    val id: String,
    val name: String,
    val level: Int,
    val stamina: Int,
    val reputationGain: Int,
)

data class ClanWarPanelUi(
    val showing: Boolean = false,
    val loading: Boolean = false,
    val error: String? = null,
    val running: Boolean = false,
    val currentTargetId: String = "",
    val currentTargetName: String = "",
    val clan: ClanWarClanInfoUi = ClanWarClanInfoUi(),
    val character: ClanWarCharacterInfoUi = ClanWarCharacterInfoUi(),
    val warList: List<ClanWarWarItemUi> = emptyList(),
    val memberList: List<ClanWarMemberUi> = emptyList(),
    val selectedRecruiters: List<String> = emptyList(),
    val bleedingReputationGained: Boolean = false,
)

data class RiftVerificationUi(
    val required: Boolean = false,
    val message: String = "",
)

data class UiState(
    val buildNumber: String = "V420.69",
    val versionMessage: String = "Checking panel status...",
    val versionChecked: Boolean = true,
    val startupReady: Boolean = true,
    val startupFailureTitle: String = "Startup Failed",
    val showBaseGameSelection: Boolean = true,
    val showServerSelection: Boolean = true,
    val currentBaseGame: BaseGameOption? = null,
    val baseGames: List<BaseGameOption> = emptyList(),
    val currentAmfProfile: AmfProfileOption? = null,
    val amfProfiles: List<AmfProfileOption> = emptyList(),
    val username: String = "",
    val password: String = "",
    val hasQuickLogin: Boolean = false,
    val characters: List<CharacterOption> = emptyList(),
    val character: CharacterSummary? = null,
    val actions: List<ActionUi> = emptyList(),
    val selectedEnemies: Map<String, String> = emptyMap(),
    val logs: List<LogEntry> = emptyList(),
    val running: Boolean = false,
    val runningAction: String? = null,
    val actionStateSyncing: Boolean = false,
    val isBusy: Boolean = false,
    val statusMessage: String? = null,
    val forceAmfSupportCurrentVersion: Boolean = true,
    val serverVersionCompatible: Boolean = true,
    val serverVersionDialogMessage: String? = null,
    val riftVerification: RiftVerificationUi = RiftVerificationUi(),
    val sageSettings: SageSettingsUi = SageSettingsUi(),
    val riftSettings: RiftSettingsUi = RiftSettingsUi(),
    val riftSkillOptions: List<RiftSkillOption> = emptyList(),
    val ninjaSagaSettings: NinjaSagaSettingsUi = NinjaSagaSettingsUi(),
    val showNinjaSagaWebLogin: Boolean = false,
    val clanWarCaptcha: ClanWarCaptchaUi = ClanWarCaptchaUi(),
    val clanWarPanel: ClanWarPanelUi = ClanWarPanelUi(),
    val billingChecking: Boolean = false,
    val billingRemainingMillis: Long = Long.MAX_VALUE,
    val billingExpiryMillis: Long = Long.MAX_VALUE,
    val hasBillingAccess: Boolean = true,
    val billingUsername: String? = null,
    val billingSubscriptionActive: Boolean = true,
    val billingDisableAds: Boolean = true,
)

class AppViewModel(application: Application) : AndroidViewModel(application) {
    private val bridge = PythonBridge(application)
    private val secureCredentialsStore = SecureCredentialsStore(application)
    private val _uiState = MutableStateFlow(UiState())
    val uiState: StateFlow<UiState> = _uiState.asStateFlow()

    private val billingRepository = BillingTimeRepository(application)
    private var billingRefreshTick = 0
    private var pollJob: Job? = null
    private var lastClanWarCaptchaRequired = false
    private var pendingClanWarCaptchaAlertMessage: String? = null

    init {
        if (SecurityUtils.isRunningOnLikelyUnsafeDevice(application)) {
            _uiState.value = _uiState.value.copy(
                statusMessage = "Security warning: rooted or debuggable environment detected",
            )
        }
        refreshStartupStatus()
        refreshState()
        startPolling()
    }

    fun onAppForegrounded() {
        val previous = _uiState.value
        _uiState.value = previous.copy(
            actionStateSyncing = previous.running || previous.runningAction != null,
        )
        refreshState()
    }

    fun updateUsername(value: String) {
        _uiState.value = _uiState.value.copy(username = value)
    }

    fun updatePassword(value: String) {
        _uiState.value = _uiState.value.copy(password = value)
    }

    fun chooseEnemy(actionKey: String, enemyId: String) {
        val updated = _uiState.value.selectedEnemies.toMutableMap()
        updated[actionKey] = enemyId
        _uiState.value = _uiState.value.copy(selectedEnemies = updated)
    }

    private fun quickLoginStorageKey(): String {
        val baseGameId = _uiState.value.currentBaseGame?.id.orEmpty()
        val profileId = _uiState.value.currentAmfProfile?.id.orEmpty()
        if (baseGameId.isBlank() || profileId.isBlank()) return profileId
        return "${baseGameId}__${profileId}"
    }

    fun login() = runBridge("login") {
        bridge.call("login", _uiState.value.username, _uiState.value.password).also { result ->
            if (result.optBoolean("success")) {
                quickLoginStorageKey().let { profileKey ->
                    secureCredentialsStore.save(profileKey, _uiState.value.username, _uiState.value.password)
                }
            }
        }
    }

    fun quickLogin() = runBridge("quickLogin") {
        val profileKey = quickLoginStorageKey()
        val creds = secureCredentialsStore.load(profileKey)
        if (creds == null) {
            JSONObject()
                .put("success", false)
                .put("message", "No quick login saved on this device for the selected server")
        } else {
            bridge.call("login", creds.first, creds.second)
        }
    }

    fun verifyRiftCode(code: String) = runBridge("verifyRiftCode") {
        bridge.call("verify_rift_code", code)
    }

    fun selectCharacter(index: Int) = runBridge("selectCharacter") {
        bridge.call("select_character", index)
    }

    fun openNinjaSagaWebLogin() {
        _uiState.value = _uiState.value.copy(showNinjaSagaWebLogin = true, statusMessage = null)
    }

    fun closeNinjaSagaWebLogin() {
        _uiState.value = _uiState.value.copy(showNinjaSagaWebLogin = false)
    }

    fun loginWithNinjaSagaWebAuth(
        fbUid: String,
        fbName: String,
        fbAt: String,
        fbSig: String,
        hashTime: String,
        time: Int = 0,
        cookieHeader: String = "",
    ) = runBridge("loginNinjaSagaWebAuth") {
        if (cookieHeader.isNotBlank()) {
            bridge.call("sync_ninjasaga_web_cookies", cookieHeader)
        }
        bridge.call("login_ninjasaga_web_auth", fbUid, fbName, fbAt, fbSig, hashTime, time)
    }

    fun refreshCharacter() = runBridge("refreshCharacter") {
        bridge.call("refresh_character")
    }

    fun changeCharacter() = runBridge("changeCharacter") {
        bridge.call("clear_selected_character")
    }

    fun selectAmfProfile(profileId: String) = runBridge("selectAmfProfile") {
        bridge.call("select_amf_profile", profileId)
    }

    fun selectBaseGame(baseGameId: String) = runBridge("selectBaseGame") {
        bridge.call("select_base_game", baseGameId)
    }

    fun continueFromBaseGameSelection() {
        _uiState.value = _uiState.value.copy(
            showBaseGameSelection = false,
            showServerSelection = true,
            statusMessage = null,
        )
    }

    private fun continueWithOfficialServerForFree() {
        _uiState.value = _uiState.value.copy(isBusy = true, statusMessage = "Selecting official server...")
        val profilesResult = bridge.call("get_amf_profiles")
        val profiles = profilesResult.optJSONArray("profiles").toAmfProfiles()
        val currentProfile = profilesResult.optJSONObject("current").toAmfProfileOption()
        val officialProfile = profiles.firstOrNull { it.id == "official" } ?: currentProfile
        if (officialProfile != null && currentProfile?.id != officialProfile.id) {
            bridge.call("select_amf_profile", officialProfile.id)
        }

        if (_uiState.value.forceAmfSupportCurrentVersion) {
            _uiState.value = _uiState.value.copy(
                isBusy = false,
                currentAmfProfile = officialProfile ?: currentProfile,
                versionMessage = "Panel OK | Panel version ${_uiState.value.buildNumber} | AMF version check skipped",
                showBaseGameSelection = false,
                showServerSelection = false,
                statusMessage = "Official server selected. Version check skipped.",
                serverVersionCompatible = true,
                serverVersionDialogMessage = null,
            )
            return
        }

        val versionResult = bridge.call("check_version")
        val versionSuccess = versionResult.optBoolean("success")
        val checkedProfile = versionResult.optJSONObject("current_amf_profile").toAmfProfileOption()
            ?: officialProfile
            ?: currentProfile
        val gameVersion = versionResult.optString("game_version", "").removeSuffix(".0")
        val configuredBuild = versionResult.optString("configured_build").ifBlank { checkedProfile?.buildNum.orEmpty() }
        val statusMessage = if (versionSuccess) {
            "Official server ready: ${checkedProfile?.label ?: "Game Server"}"
        } else {
            buildString {
                append(versionResult.optString("message", "Failed to check game version"))
                if (checkedProfile != null) {
                    append(" | Server: ")
                    append(checkedProfile.label)
                }
                if (configuredBuild.isNotBlank()) {
                    append(" | Config build: ")
                    append(configuredBuild)
                }
            }
        }
        _uiState.value = _uiState.value.copy(
            isBusy = false,
            currentAmfProfile = checkedProfile,
            versionMessage = if (versionSuccess) {
                "Panel OK | Panel version ${_uiState.value.buildNumber} | Game version $gameVersion"
            } else {
                "Version check failed: $statusMessage"
            },
            showBaseGameSelection = false,
            showServerSelection = false,
            statusMessage = statusMessage,
            serverVersionCompatible = versionSuccess,
            serverVersionDialogMessage = if (versionSuccess) null else statusMessage,
        )
    }

    fun updateForceAmfSupportCurrentVersion(enabled: Boolean) {
        _uiState.value = _uiState.value.copy(
            forceAmfSupportCurrentVersion = enabled,
            serverVersionCompatible = if (enabled) true else _uiState.value.serverVersionCompatible,
            serverVersionDialogMessage = if (enabled) null else _uiState.value.serverVersionDialogMessage,
            statusMessage = if (enabled) {
                "AMF version check will be skipped for the selected server"
            } else {
                _uiState.value.statusMessage
            },
        )
    }

    fun continueFromServerSelection() {
        val currentProfile = _uiState.value.currentAmfProfile
        if (_uiState.value.forceAmfSupportCurrentVersion) {
            _uiState.value = _uiState.value.copy(
                isBusy = false,
                currentAmfProfile = currentProfile,
                versionMessage = buildString {
                    append("Panel OK | Panel version ")
                    append(_uiState.value.buildNumber)
                    append(" | AMF version check skipped")
                },
                showBaseGameSelection = false,
                showServerSelection = false,
                statusMessage = "Server ready: ${currentProfile?.label ?: "Game Server"}",
                serverVersionCompatible = true,
                serverVersionDialogMessage = null,
            )
            return
        }

        viewModelScope.launch(Dispatchers.IO) {
            try {
                _uiState.value = _uiState.value.copy(isBusy = true, statusMessage = null, serverVersionDialogMessage = null)
                val result = bridge.call("check_version")
                val success = result.optBoolean("success")
                val currentProfile = result.optJSONObject("current_amf_profile").toAmfProfileOption() ?: _uiState.value.currentAmfProfile
                val gameVersion = result.optString("game_version", "").removeSuffix(".0")
                val configuredBuild = result.optString("configured_build").ifBlank { currentProfile?.buildNum.orEmpty() }
                val statusMessage = if (success) {
                    "Server ready: ${currentProfile?.label ?: "Game Server"}"
                } else {
                    buildString {
                        append(result.optString("message", "Failed to check game version"))
                        if (currentProfile != null) {
                            append(" | Server: ")
                            append(currentProfile.label)
                        }
                        if (configuredBuild.isNotBlank()) {
                            append(" | Config build: ")
                            append(configuredBuild)
                        }
                    }
                }

                _uiState.value = _uiState.value.copy(
                    isBusy = false,
                    currentAmfProfile = currentProfile,
                    versionMessage = if (success) {
                        "Panel OK | Panel version ${_uiState.value.buildNumber} | Game version $gameVersion"
                    } else {
                        "Version check failed: $statusMessage"
                    },
                    showBaseGameSelection = false,
                    showServerSelection = false,
                    statusMessage = statusMessage,
                    serverVersionCompatible = success,
                    serverVersionDialogMessage = if (success) null else statusMessage,
                )
            } catch (t: Throwable) {
                _uiState.value = _uiState.value.copy(
                    isBusy = false,
                    showBaseGameSelection = false,
                    showServerSelection = true,
                    serverVersionCompatible = false,
                    statusMessage = "Version check crashed for this server: ${t.message ?: t.javaClass.simpleName}",
                    serverVersionDialogMessage = "Version check crashed for this server: ${t.message ?: t.javaClass.simpleName}",
                )
            }
        }
    }

    fun dismissServerVersionDialog() {
        _uiState.value = _uiState.value.copy(serverVersionDialogMessage = null)
    }

    fun openServerSelection() {
        _uiState.value = _uiState.value.copy(showBaseGameSelection = false, showServerSelection = true)
    }

    fun openBaseGameSelection() {
        _uiState.value = _uiState.value.copy(
            showBaseGameSelection = true,
            showServerSelection = false,
        )
    }

    fun startAction(action: ActionUi) = runBridge("startAction") {
        if (_uiState.value.running || _uiState.value.actionStateSyncing) {
            return@runBridge JSONObject()
                .put("success", false)
                .put("message", "Another action is already running or syncing. Please wait.")
        }
        val currentState = bridge.call("get_state")
        if (currentState.optBoolean("success") && currentState.optBoolean("running")) {
            applyState(currentState)
            return@runBridge JSONObject()
                .put("success", false)
                .put("message", "Another action is already running.")
        }
        val selectedEnemy = _uiState.value.selectedEnemies[action.key]
        val params = JSONObject()
        if (selectedEnemy != null) {
            params.put("enemy_id", selectedEnemy)
        }
        bridge.call("start_action", action.key, params.toString())
    }

    fun openClanWarPanel(forceRefresh: Boolean = false) {
        val currentPanel = _uiState.value.clanWarPanel
        if (!forceRefresh) {
            val hasCache = currentPanel.warList.isNotEmpty() ||
                currentPanel.memberList.isNotEmpty() ||
                currentPanel.clan.id.isNotBlank() ||
                currentPanel.clan.name != "Unknown Clan"
            if (hasCache) {
                _uiState.value = _uiState.value.copy(
                    clanWarPanel = currentPanel.copy(showing = true, loading = false, error = null),
                    statusMessage = null,
                )
                return
            }
        }
        if (currentPanel.loading) return
        viewModelScope.launch(Dispatchers.IO) {
            _uiState.value = _uiState.value.copy(
                clanWarPanel = currentPanel.copy(showing = true, loading = true, error = null),
            )
            val result = bridge.call("open_clan_war")
            val state = bridge.call("get_state")
            if (state.optBoolean("success")) {
                applyState(state)
            }
            _uiState.value = _uiState.value.copy(
                clanWarPanel = _uiState.value.clanWarPanel.copy(
                    showing = true,
                    loading = false,
                    error = if (result.optBoolean("success")) null else result.optString("message", "Failed to load Clan War"),
                ),
                statusMessage = if (result.optBoolean("success")) "Clan War panel loaded" else result.optString("message", "Failed to load Clan War"),
            )
        }
    }

    fun refreshClanWarPanel() {
        openClanWarPanel(forceRefresh = true)
    }

    fun closeClanWarPanel() {
        _uiState.value = _uiState.value.copy(
            clanWarPanel = _uiState.value.clanWarPanel.copy(showing = false, loading = false, error = null),
        )
    }

    fun startClanWar() = runBridge("startClanWar") {
        bridge.call("start_clan_war")
    }.also {
        _uiState.value = _uiState.value.copy(
            clanWarPanel = _uiState.value.clanWarPanel.copy(showing = false, loading = false, error = null),
        )
    }

    fun startClanWarFromSelection(targetClanId: String, targetClanName: String, recruitIds: List<String>) {
        val current = _uiState.value.ninjaSagaSettings
        val cleanedTargetId = targetClanId.trim()
        val cleanedTargetName = targetClanName.trim()
        val cleanedRecruits = recruitIds.map { it.trim() }.filter { it.isNotBlank() }.take(2)
        val nextSettings = current.copy(
            clanWarTargetClanId = cleanedTargetId,
            clanWarTargetClanName = cleanedTargetName,
            clanWarManualRecruit = current.clanWarManualRecruit && cleanedRecruits.isNotEmpty(),
            clanWarManualMemberIds = if (current.clanWarManualRecruit) cleanedRecruits.joinToString(",") else "",
        )
        applyClanWarPanelSettings(nextSettings, startAfterSave = true)
    }

    fun loadNinjaSagaSettings() = runBridge("loadNinjaSagaSettings") {
        val isZenshin = _uiState.value.currentBaseGame?.id == "zenshin"
        bridge.call(if (isZenshin) "get_zenshin_settings" else "get_ninjasaga_settings")
    }

    fun loadSageSettings() = runBridge("loadSageSettings") {
        bridge.call("get_sage_settings")
    }

    fun loadRiftSettings() = runBridge("loadRiftSettings") {
        bridge.call("get_rift_settings")
    }

    fun saveSageSettings(settings: SageSettingsUi) = runBridge("saveSageSettings") {
        val payload = JSONObject()
            .put("leveling_delay_seconds", settings.generalActionDelaySeconds)
            .put("leveling_cycle_cooldown_seconds", settings.cycleCooldownSeconds)
            .put("leveling_rest_every_cycles", settings.restEveryCycles)
            .put("leveling_rest_duration_seconds", settings.restDurationSeconds)
            .put("leveling_action_jitter_seconds", settings.actionJitterSeconds)
            .put("leveling_min_call_delay_seconds", settings.minCallDelaySeconds)
            .put("leveling_start_retry_delay_seconds", settings.startRetryDelaySeconds)
            .put("leveling_start_max_retries", settings.startMaxRetries)
            .put("leveling_failure_window_seconds", settings.failureWindowSeconds)
            .put("leveling_max_failures_in_window", settings.maxFailuresInWindow)
            .put("leveling_circuit_cooldown_seconds", settings.circuitCooldownSeconds)
            .put("sage_exam_start_delay_seconds", settings.examStartDelaySeconds)
            .put("sage_exam_finish_delay_seconds", settings.examFinishDelaySeconds)
            .put("sage_battle_wait_seconds", settings.battleDurationDelaySeconds)
            .put("sage_post_finish_delay_seconds", settings.afterFinishDelaySeconds)
            .put("sage_auto_relogin_wait_seconds", settings.autoReloginWaitSeconds)
            .put("sage_infinite_loop_rest_every_cycles", settings.infiniteLoopRestEveryMissions)
            .put("sage_infinite_loop_rest_duration_seconds", settings.infiniteLoopRestDurationSeconds)
            .put("sage_limited_loop_rest_every_cycles", settings.limitedLoopRestEveryMissions)
            .put("sage_limited_loop_rest_duration_seconds", settings.limitedLoopRestDurationSeconds)
            .put("sage_special_jounin_class_skill", settings.specialJouninClassSkill)
            .put("sage_event_empty_resource_mode", settings.eventResourceMode)
            .put("sage_event_wait_minutes", settings.eventWaitMinutes)
            .put("sage_aniv_event_empty_resource_mode", settings.anivEventResourceMode)
            .put("sage_aniv_event_wait_minutes", settings.anivEventWaitMinutes)
            .put("sage_sakura_event_empty_resource_mode", settings.sakuraEventResourceMode)
            .put("sage_sakura_event_wait_minutes", settings.sakuraEventWaitMinutes)
            .put("sage_easter_event_empty_resource_mode", settings.easterEventResourceMode)
            .put("sage_easter_event_wait_minutes", settings.easterEventWaitMinutes)
            .put("sage_shadow_war_empty_resource_mode", settings.shadowWarResourceMode)
            .put("sage_shadow_war_wait_minutes", settings.shadowWarWaitMinutes)
            .put("clan_war_auto_spend_token", settings.clanWarAutoSpendToken)
            .put("clan_war_stamina_refill_source", settings.clanWarStaminaRefillSource)
            .put("clan_war_battle_delay_seconds", settings.clanWarBattleDelaySeconds)
            .put("clan_war_buy_stamina_delay_seconds", settings.clanWarBuyStaminaDelaySeconds)
        bridge.call("set_sage_settings", payload.toString())
    }

    fun saveRiftSettings(settings: RiftSettingsUi) = runBridge("saveRiftSettings") {
        val payload = JSONObject()
            .put("rift_min_call_delay_seconds", settings.minCallDelaySeconds)
            .put("rift_loop_delay_seconds", settings.loopDelaySeconds)
            .put("rift_auto_relogin_wait_seconds", settings.autoReloginWaitSeconds)
            .put("rift_infinite_loop_rest_every_cycles", settings.infiniteLoopRestEveryCycles)
            .put("rift_infinite_loop_rest_duration_seconds", settings.infiniteLoopRestDurationSeconds)
            .put("rift_limited_loop_rest_every_cycles", settings.limitedLoopRestEveryCycles)
            .put("rift_limited_loop_rest_duration_seconds", settings.limitedLoopRestDurationSeconds)
            .put("rift_mission_battle_wait_base_seconds", settings.missionBattleWaitBaseSeconds)
            .put("rift_mission_battle_wait_random_seconds", settings.missionBattleWaitRandomSeconds)
            .put("rift_event_battle_wait_base_seconds", settings.eventBattleWaitBaseSeconds)
            .put("rift_event_battle_wait_random_seconds", settings.eventBattleWaitRandomSeconds)
            .put("rift_eudemon_battle_wait_base_seconds", settings.eudemonBattleWaitBaseSeconds)
            .put("rift_eudemon_battle_wait_random_seconds", settings.eudemonBattleWaitRandomSeconds)
            .put("rift_eudemon_between_battles_delay_seconds", settings.eudemonBetweenBattlesDelaySeconds)
            .put("rift_hunting_house_battle_wait_base_seconds", settings.huntingHouseBattleWaitBaseSeconds)
            .put("rift_hunting_house_battle_wait_random_seconds", settings.huntingHouseBattleWaitRandomSeconds)
            .put("rift_hunting_house_between_battles_delay_seconds", settings.huntingHouseBetweenBattlesDelaySeconds)
            .put("rift_exam_wait_min_seconds", settings.examWaitMinSeconds)
            .put("rift_exam_wait_max_seconds", settings.examWaitMaxSeconds)
            .put("rift_exam_stage_gap_seconds", settings.examStageGapSeconds)
            .put("rift_special_jounin_class_skill", settings.specialJouninClassSkill)
            .put("rift_event_empty_resource_mode", settings.eventResourceMode)
            .put("rift_event_wait_minutes", settings.eventWaitMinutes)
            .put("rift_hanami_event_empty_resource_mode", settings.hanamiEventResourceMode)
            .put("rift_hanami_event_wait_minutes", settings.hanamiEventWaitMinutes)
            .put("rift_easter_event_empty_resource_mode", settings.easterEventResourceMode)
            .put("rift_easter_event_wait_minutes", settings.easterEventWaitMinutes)
        bridge.call("set_rift_settings", payload.toString())
    }

    private fun buildNinjaSagaSettingsPayload(settings: NinjaSagaSettingsUi): JSONObject {
        return JSONObject()
            .put("leveling_action_delay_seconds", settings.levelingActionDelaySeconds)
            .put("leveling_cycle_cooldown_seconds", settings.levelingCycleCooldownSeconds)
            .put("leveling_rest_every_cycles", settings.levelingRestEveryCycles)
            .put("leveling_rest_duration_seconds", settings.levelingRestDurationSeconds)
            .put("leveling_action_jitter_seconds", settings.levelingActionJitterSeconds)
            .put("leveling_min_call_delay_seconds", settings.levelingMinCallDelaySeconds)
            .put("leveling_start_retry_delay_seconds", settings.levelingStartRetryDelaySeconds)
            .put("leveling_start_max_retries", settings.levelingStartMaxRetries)
            .put("leveling_cloudflare_rest_seconds", settings.levelingCloudflareRestSeconds)
            .put("leveling_cloudflare_backoff_steps_seconds", settings.levelingCloudflareBackoffSteps)
            .put("leveling_failure_window_seconds", settings.levelingFailureWindowSeconds)
            .put("leveling_max_failures_in_window", settings.levelingMaxFailuresInWindow)
            .put("leveling_circuit_cooldown_seconds", settings.levelingCircuitCooldownSeconds)
            .put("eudemon_start_finish_delay_seconds", settings.eudemonStartFinishDelaySeconds)
            .put("eudemon_cycle_cooldown_seconds", settings.eudemonCycleCooldownSeconds)
            .put("easter_battle_delay_seconds", settings.easterBattleDelaySeconds)
            .put("easter_cycle_cooldown_seconds", settings.easterCycleCooldownSeconds)
            .put("sakura_battle_delay_seconds", settings.sakuraBattleDelaySeconds)
            .put("easter_auto_spend_enabled", settings.easterAutoSpendEnabled)
            .put("easter_auto_spend_max_refills_per_run", settings.easterAutoSpendMaxRefillsPerRun)
            .put("easter_auto_spend_buy_amount", settings.easterAutoSpendBuyAmount)
            .put("event_resource_mode", settings.eventResourceMode)
            .put("event_wait_minutes", settings.eventWaitMinutes)
            .put("special_jounin_class_index", settings.specialJouninClassIndex)
            .put("tp_training_abuse_loop", settings.tpTrainingAbuseLoop)
            .put("ss_training_abuse_loop", settings.ssTrainingAbuseLoop)
            .put("clan_war_auto_spend_token", settings.clanWarAutoSpendToken)
            .put("clan_war_stamina_refill_source", settings.clanWarStaminaRefillSource)
            .put("clan_war_bleeding_mode", settings.clanWarBleedingMode)
            .put("clan_war_manual_recruit", settings.clanWarManualRecruit)
            .put("clan_war_manual_member_ids", settings.clanWarManualMemberIds.split(",").map { it.trim() }.filter { it.isNotBlank() })
            .put("clan_war_target_clan_id", settings.clanWarTargetClanId)
            .put("clan_war_target_clan_name", settings.clanWarTargetClanName)
            .put("clan_war_battle_delay_seconds", settings.clanWarBattleDelaySeconds)
            .put("clan_war_refresh_delay_seconds", settings.clanWarRefreshDelaySeconds)
            .put("clan_war_buy_stamina_delay_seconds", settings.clanWarBuyStaminaDelaySeconds)
            .put("clan_war_amf_call_delay_seconds", settings.clanWarAmfCallDelaySeconds)
            .put("clan_war_post_captcha_resume_delay_seconds", settings.clanWarPostCaptchaResumeDelaySeconds)
            .put("clan_war_low_stamina_wait_minutes", settings.clanWarLowStaminaWaitMinutes)
    }

    fun saveNinjaSagaSettings(settings: NinjaSagaSettingsUi) = runBridge("saveNinjaSagaSettings") {
        val payload = buildNinjaSagaSettingsPayload(settings)
        val isZenshin = _uiState.value.currentBaseGame?.id == "zenshin"
        bridge.call(if (isZenshin) "set_zenshin_settings" else "set_ninjasaga_settings", payload.toString())
    }

    fun applyClanWarPanelSettings(settings: NinjaSagaSettingsUi, refreshAfterSave: Boolean = false, startAfterSave: Boolean = false) {
        viewModelScope.launch(Dispatchers.IO) {
            _uiState.value = _uiState.value.copy(isBusy = true, statusMessage = null)
            val isZenshin = _uiState.value.currentBaseGame?.id == "zenshin"
            val saveResult = bridge.call(
                if (isZenshin) "set_zenshin_settings" else "set_ninjasaga_settings",
                buildNinjaSagaSettingsPayload(settings).toString(),
            )
            var terminalResult = saveResult
            if (saveResult.optBoolean("success") && refreshAfterSave) {
                terminalResult = bridge.call("open_clan_war")
            }
            if (saveResult.optBoolean("success") && startAfterSave) {
                terminalResult = bridge.call("start_clan_war")
            }
            val state = bridge.call("get_state")
            if (state.optBoolean("success")) {
                applyState(state)
            }
            val latestSettings = bridge.call(if (isZenshin) "get_zenshin_settings" else "get_ninjasaga_settings")
            if (latestSettings.optBoolean("success")) {
                _uiState.value = _uiState.value.copy(
                    ninjaSagaSettings = latestSettings.optJSONObject("settings").toNinjaSagaSettingsUi(),
                )
            }
            _uiState.value = _uiState.value.copy(
                isBusy = false,
                clanWarPanel = _uiState.value.clanWarPanel.copy(
                    showing = !startAfterSave,
                    loading = false,
                    error = if (terminalResult.optBoolean("success")) null else terminalResult.optString("message", "Clan War request failed"),
                ),
                statusMessage = if (terminalResult.optBoolean("success")) {
                    when {
                        startAfterSave -> "Clan War started"
                        refreshAfterSave -> "Clan War settings saved and refreshed"
                        else -> "Clan War settings saved"
                    }
                } else {
                    terminalResult.optString("message", "Clan War request failed")
                },
            )
        }
    }

    fun loadClanWarCaptchaChallenge(cookieHeader: String = "") {
        val current = _uiState.value.clanWarCaptcha
        if (current.loading || current.verifying) return
        viewModelScope.launch(Dispatchers.IO) {
            _uiState.value = _uiState.value.copy(
                clanWarCaptcha = current.copy(loading = true, error = null, submittedAnswer = null),
            )
            if (cookieHeader.isNotBlank()) {
                bridge.call("sync_ninjasaga_web_cookies", cookieHeader)
            }
            val webContextResult = bridge.call("get_ninjasaga_captcha_web_context")
            val state = bridge.call("get_state")
            if (state.optBoolean("success")) {
                applyState(state)
            }
            val success = webContextResult.optBoolean("success")
            val message = webContextResult.optString("message")
            val wrappedChallenge = if (success) {
                JSONObject().apply {
                    put("web_context", webContextResult)
                    put("reload_token", System.currentTimeMillis())
                }.toString()
            } else {
                null
            }
            _uiState.value = _uiState.value.copy(
                clanWarCaptcha = _uiState.value.clanWarCaptcha.copy(
                    loading = false,
                    verifying = false,
                    challengeJson = wrappedChallenge,
                    error = if (success) null else message.ifBlank { "Failed to load captcha challenge" },
                    message = if (message.isNotBlank()) message else _uiState.value.clanWarCaptcha.message,
                ),
            )
        }
    }

    fun handleClanWarCaptchaGenerateResult(resultJson: String) {
        viewModelScope.launch(Dispatchers.IO) {
            val result = try {
                JSONObject(resultJson)
            } catch (_: Throwable) {
                JSONObject()
            }
            val debugObject = result.optJSONObject("debug")
            val debugJson = debugObject?.toString(2)
            val success = result.optBoolean("success") && result.optJSONObject("challenge") != null
            val message = result.optString("message")
            _uiState.value = _uiState.value.copy(
                clanWarCaptcha = _uiState.value.clanWarCaptcha.copy(
                    loading = false,
                    verifying = false,
                    error = if (success) null else message.ifBlank { "Failed to load captcha challenge" },
                    message = if (message.isNotBlank()) message else _uiState.value.clanWarCaptcha.message,
                    debugJson = debugJson ?: _uiState.value.clanWarCaptcha.debugJson,
                ),
            )
        }
    }

    fun submitClanWarCaptchaWebResult(resultJson: String, cookieHeader: String = "") {
        val current = _uiState.value.clanWarCaptcha
        if (current.verifying) return
        viewModelScope.launch(Dispatchers.IO) {
            val resultObject = try {
                JSONObject(resultJson)
            } catch (_: Throwable) {
                JSONObject()
            }
            val submittedAnswer = try {
                resultObject.optString("answer").takeIf { it.isNotBlank() }
            } catch (_: Throwable) {
                null
            }
            _uiState.value = _uiState.value.copy(
                clanWarCaptcha = current.copy(verifying = true, error = null, submittedAnswer = submittedAnswer),
            )
            if (cookieHeader.isNotBlank()) {
                bridge.call("sync_ninjasaga_web_cookies", cookieHeader)
            }
            val bridgeResult = bridge.call("clan_war_captcha_web_result", resultJson)
            val resultClanWar = bridgeResult.optJSONObject("clan_war")
            val resultCaptchaDebug = resultClanWar?.optJSONObject("captcha_debug")
            val immediateDebugJson = resultCaptchaDebug?.toString(2)
                ?: resultObject.optJSONObject("debug")?.toString(2)
                ?: JSONObject().apply {
                    put("verify_response", resultObject)
                }.toString(2)
            val state = bridge.call("get_state")
            if (state.optBoolean("success")) {
                applyState(state)
            }
            val success = bridgeResult.optBoolean("success")
            val message = bridgeResult.optString("message")
            if (success) {
                _uiState.value = _uiState.value.copy(
                    clanWarCaptcha = _uiState.value.clanWarCaptcha.copy(
                        required = false,
                        verifying = false,
                        loading = false,
                        challengeJson = null,
                        message = if (message.isNotBlank()) message else _uiState.value.clanWarCaptcha.message,
                        error = null,
                        debugJson = immediateDebugJson,
                        submittedAnswer = submittedAnswer,
                    ),
                )
            } else {
                val normalizedError = when {
                    message.contains("Incorrect", ignoreCase = true) -> "Wrong captcha. Loading new challenge..."
                    message.contains("Verification failed", ignoreCase = true) -> "Captcha verify failed. Loading new challenge..."
                    else -> message.ifBlank { "Captcha verification failed. Loading new challenge..." }
                }
                _uiState.value = _uiState.value.copy(
                    clanWarCaptcha = _uiState.value.clanWarCaptcha.copy(
                        verifying = false,
                        loading = false,
                        message = if (message.isNotBlank()) message else _uiState.value.clanWarCaptcha.message,
                        error = normalizedError,
                        debugJson = immediateDebugJson,
                    ),
                )
                delay(1000)
                loadClanWarCaptchaChallenge(cookieHeader)
            }
        }
    }

    fun failClanWarCaptchaBrowser(message: String) {
        _uiState.value = _uiState.value.copy(
            clanWarCaptcha = _uiState.value.clanWarCaptcha.copy(
                loading = false,
                verifying = false,
                challengeJson = null,
                error = message.ifBlank { "Browser session expired. Please log in again." },
            ),
        )
    }

    fun stopAction() = runBridge("stopAction") {
        bridge.call("stop_action")
    }

    fun clearLogs() = runBridge("clearLogs") {
        bridge.call("clear_logs")
    }

    fun logout() = runBridge("logout") {
        bridge.call("logout")
    }

    fun loginBilling(username: String, password: String) {
        refreshBillingStatus(showChecking = true)
    }

    fun logoutBilling() {
        refreshBillingStatus()
    }

    fun refreshBillingStatus(showChecking: Boolean = false) {
        viewModelScope.launch(Dispatchers.IO) {
            if (showChecking) {
                _uiState.value = _uiState.value.copy(billingChecking = true, statusMessage = "Refreshing subscription...")
            }
            val snapshot = billingRepository.refresh()
            applyBillingSnapshot(snapshot)
            if (showChecking) {
                _uiState.value = _uiState.value.copy(
                    billingChecking = false,
                    statusMessage = if (snapshot.subscriptionActive) {
                        "Subscription refreshed"
                    } else {
                        "Subscription refreshed. Free mode is active."
                    },
                )
            }
        }
    }

    fun grantRewardBillingTime(hours: Int = 2) {
        viewModelScope.launch(Dispatchers.IO) {
            _uiState.value = _uiState.value.copy(isBusy = true)
            val snapshot = billingRepository.grantRewardHours(hours)
            _uiState.value = _uiState.value.copy(
                isBusy = false,
                billingRemainingMillis = snapshot.remainingMillis,
                hasBillingAccess = snapshot.hasAccess,
                statusMessage = "Added +$hours hours billing time",
            )
        }
    }

    private fun applyBillingSnapshot(snapshot: BillingSnapshot) {
        val previousState = _uiState.value
        val shouldStopRunningAction = previousState.hasBillingAccess && !snapshot.hasAccess && previousState.running
        val shouldLeaveAlternativeServer = !snapshot.subscriptionActive && previousState.currentAmfProfile?.id != null && previousState.currentAmfProfile.id != "official"

        _uiState.value = previousState.copy(
            billingRemainingMillis = snapshot.remainingMillis,
            billingExpiryMillis = snapshot.expiryMillis,
            hasBillingAccess = snapshot.hasAccess,
            billingUsername = snapshot.username,
            billingSubscriptionActive = snapshot.subscriptionActive,
            billingDisableAds = snapshot.disableAds,
            characters = if (shouldLeaveAlternativeServer) emptyList() else previousState.characters,
            character = if (shouldLeaveAlternativeServer) null else previousState.character,
            showBaseGameSelection = if (shouldLeaveAlternativeServer) true else previousState.showBaseGameSelection,
            showServerSelection = if (shouldLeaveAlternativeServer) false else previousState.showServerSelection,
            statusMessage = if (shouldLeaveAlternativeServer) {
                "Subscription expired. Alternative servers require subscription."
            } else if (shouldStopRunningAction) {
                "Billing expired. Current action stopped."
            } else if (!snapshot.hasAccess && previousState.character != null && !previousState.running) {
                previousState.statusMessage ?: "Billing expired. Watch a rewarded ad to add +2 hours."
            } else {
                previousState.statusMessage
            },
        )

        if (shouldStopRunningAction) {
            bridge.call("stop_action")
            val state = bridge.call("get_state")
            if (state.optBoolean("success")) {
                applyState(state)
            }
        }
        if (shouldLeaveAlternativeServer) {
            bridge.call("stop_action")
            bridge.call("clear_selected_character")
            bridge.call("select_amf_profile", "official")
            _uiState.value = _uiState.value.copy(
                characters = emptyList(),
                character = null,
                currentAmfProfile = null,
                showBaseGameSelection = true,
                showServerSelection = false,
                running = false,
                runningAction = null,
                actionStateSyncing = false,
                statusMessage = "Subscription expired. Alternative servers require subscription.",
            )
        }
    }

    private fun refreshStartupStatus() {
        viewModelScope.launch(Dispatchers.IO) {
            val result = bridge.call("startup_check")
            val buildNumber = result.optString("build", _uiState.value.buildNumber)
            val failureMessage = result.optString("message")
            val baseGames = result.optJSONArray("base_games").toBaseGames()
            val currentBaseGame = result.optJSONObject("current_base_game").toBaseGameOption()
            val currentProfile = result.optJSONObject("current_amf_profile").toAmfProfileOption()
            val amfProfiles = result.optJSONArray("amf_profiles").toAmfProfiles()
            val loginKey = run {
                val baseId = (currentBaseGame ?: _uiState.value.currentBaseGame)?.id.orEmpty()
                val profileId = (currentProfile ?: _uiState.value.currentAmfProfile)?.id.orEmpty()
                if (baseId.isBlank() || profileId.isBlank()) profileId else "${baseId}__${profileId}"
            }
            val message = if (result.optBoolean("success")) {
                "Panel OK | Version $buildNumber"
            } else {
                "Startup check failed: $failureMessage"
            }
            val failureTitle = if (failureMessage.contains("update required", ignoreCase = true)) {
                "Update Required"
            } else if (failureMessage.contains("maintenance", ignoreCase = true)) {
                "Maintenance"
            } else if (failureMessage.contains("panel disabled", ignoreCase = true)) {
                "Panel Disabled"
            } else {
                "Startup Failed"
            }
            _uiState.value = _uiState.value.copy(
                buildNumber = buildNumber,
                versionMessage = message,
                versionChecked = true,
                startupReady = result.optBoolean("success"),
                startupFailureTitle = failureTitle,
                baseGames = if (baseGames.isNotEmpty()) baseGames else _uiState.value.baseGames,
                currentBaseGame = currentBaseGame ?: _uiState.value.currentBaseGame,
                amfProfiles = if (amfProfiles.isNotEmpty()) amfProfiles else _uiState.value.amfProfiles,
                currentAmfProfile = currentProfile ?: _uiState.value.currentAmfProfile,
                hasQuickLogin = secureCredentialsStore.hasSavedLogin(loginKey),
                showBaseGameSelection = _uiState.value.character == null,
                serverVersionCompatible = true,
                serverVersionDialogMessage = null,
            )
        }
    }

    private fun refreshState() {
        viewModelScope.launch(Dispatchers.IO) {
            val result = bridge.call("get_state")
            if (result.optBoolean("success")) {
                applyState(result)
            } else {
                _uiState.value = _uiState.value.copy(
                    actionStateSyncing = false,
                    statusMessage = result.optString("message", "Startup failed"),
                )
            }
        }
    }

    private fun runBridge(tag: String, block: suspend () -> JSONObject) {
        viewModelScope.launch(Dispatchers.IO) {
            val previousState = _uiState.value
            _uiState.value = previousState.copy(
                isBusy = true,
                statusMessage = if (previousState.running || previousState.actionStateSyncing) {
                    previousState.statusMessage
                } else {
                    null
                },
            )
            val result = block()
            val state = bridge.call("get_state")
            if (state.optBoolean("success")) {
                applyState(state)
            }
            if ((tag == "login" || tag == "quickLogin" || tag == "loginNinjaSagaWebAuth") && result.optBoolean("success")) {
                val loginCharacters = result.optJSONArray("characters").toCharacterOptions()
                if (loginCharacters.isNotEmpty()) {
                    _uiState.value = _uiState.value.copy(
                        characters = loginCharacters,
                        showBaseGameSelection = false,
                        showServerSelection = false,
                        showNinjaSagaWebLogin = false,
                    )
                }
            }
            if (tag == "verifyRiftCode" && result.optBoolean("success")) {
                val loginCharacters = result.optJSONArray("characters").toCharacterOptions()
                if (loginCharacters.isNotEmpty()) {
                    _uiState.value = _uiState.value.copy(
                        characters = loginCharacters,
                        showBaseGameSelection = false,
                        showServerSelection = false,
                    )
                }
            }
            if (tag == "selectAmfProfile") {
                val profilesResult = bridge.call("get_amf_profiles")
                if (profilesResult.optBoolean("success")) {
                    val currentProfile = profilesResult.optJSONObject("current").toAmfProfileOption()
                    val loginKey = run {
                        val baseId = _uiState.value.currentBaseGame?.id.orEmpty()
                        val profileId = currentProfile?.id.orEmpty()
                        if (baseId.isBlank() || profileId.isBlank()) profileId else "${baseId}__${profileId}"
                    }
                    _uiState.value = _uiState.value.copy(
                        amfProfiles = profilesResult.optJSONArray("profiles").toAmfProfiles(),
                        currentAmfProfile = currentProfile,
                        hasQuickLogin = secureCredentialsStore.hasSavedLogin(loginKey),
                    )
                }
            }
            if (tag == "selectBaseGame") {
                val profilesResult = bridge.call("get_amf_profiles")
                val stateResult = bridge.call("get_state")
                val currentProfile = profilesResult.optJSONObject("current").toAmfProfileOption()
                val currentBaseGame = stateResult.optJSONObject("current_base_game").toBaseGameOption()
                val baseGames = stateResult.optJSONArray("base_games").toBaseGames()
                val profiles = profilesResult.optJSONArray("profiles").toAmfProfiles()
                val loginKey = run {
                    val baseId = currentBaseGame?.id.orEmpty()
                    val profileId = currentProfile?.id.orEmpty()
                    if (baseId.isBlank() || profileId.isBlank()) profileId else "${baseId}__${profileId}"
                }
                _uiState.value = _uiState.value.copy(
                    baseGames = if (baseGames.isNotEmpty()) baseGames else _uiState.value.baseGames,
                    currentBaseGame = currentBaseGame ?: _uiState.value.currentBaseGame,
                    amfProfiles = profiles,
                    currentAmfProfile = currentProfile,
                    showBaseGameSelection = false,
                    showServerSelection = true,
                    hasQuickLogin = secureCredentialsStore.hasSavedLogin(loginKey),
                    statusMessage = "Choose a game server.",
                )
                if ((currentBaseGame ?: _uiState.value.currentBaseGame)?.id == "ninjasaga" ||
                    (currentBaseGame ?: _uiState.value.currentBaseGame)?.id == "zenshin"
                ) {
                    val settingsBridgeMethod =
                        if ((currentBaseGame ?: _uiState.value.currentBaseGame)?.id == "zenshin") {
                            "get_zenshin_settings"
                        } else {
                            "get_ninjasaga_settings"
                        }
                    val settingsResult = bridge.call(settingsBridgeMethod)
                    if (settingsResult.optBoolean("success")) {
                        _uiState.value = _uiState.value.copy(
                            ninjaSagaSettings = settingsResult.optJSONObject("settings").toNinjaSagaSettingsUi(),
                        )
                    }
                } else if ((currentBaseGame ?: _uiState.value.currentBaseGame)?.id == "sage") {
                    val settingsResult = bridge.call("get_sage_settings")
                    if (settingsResult.optBoolean("success")) {
                        _uiState.value = _uiState.value.copy(
                            sageSettings = settingsResult.optJSONObject("settings").toSageSettingsUi(),
                        )
                    }
                } else if ((currentBaseGame ?: _uiState.value.currentBaseGame)?.id == "rift") {
                    val settingsResult = bridge.call("get_rift_settings")
                    if (settingsResult.optBoolean("success")) {
                        _uiState.value = _uiState.value.copy(
                            riftSettings = settingsResult.optJSONObject("settings").toRiftSettingsUi(),
                            riftSkillOptions = settingsResult.optJSONArray("special_jounin_skill_options").toRiftSkillOptions(),
                        )
                    }
                }
                if (!_uiState.value.billingSubscriptionActive) {
                    val officialProfile = profiles.firstOrNull { it.id == "official" }
                    if (officialProfile != null && currentProfile?.id != officialProfile.id) {
                        bridge.call("select_amf_profile", officialProfile.id)
                        val officialLoginKey = run {
                            val baseId = (currentBaseGame ?: _uiState.value.currentBaseGame)?.id.orEmpty()
                            if (baseId.isBlank()) officialProfile.id else "${baseId}__${officialProfile.id}"
                        }
                        _uiState.value = _uiState.value.copy(
                            currentAmfProfile = officialProfile,
                            hasQuickLogin = secureCredentialsStore.hasSavedLogin(officialLoginKey),
                            statusMessage = "Official server is selected. Alternative servers require subscription.",
                        )
                    }
                }
            }
            if (tag == "loadSageSettings" || tag == "saveSageSettings") {
                val settingsResult = bridge.call("get_sage_settings")
                if (settingsResult.optBoolean("success")) {
                    _uiState.value = _uiState.value.copy(
                        sageSettings = settingsResult.optJSONObject("settings").toSageSettingsUi(),
                    )
                }
            }
            if (tag == "loadRiftSettings" || tag == "saveRiftSettings") {
                val settingsResult = bridge.call("get_rift_settings")
                if (settingsResult.optBoolean("success")) {
                    _uiState.value = _uiState.value.copy(
                        riftSettings = settingsResult.optJSONObject("settings").toRiftSettingsUi(),
                        riftSkillOptions = settingsResult.optJSONArray("special_jounin_skill_options").toRiftSkillOptions(),
                    )
                }
            }
            if (tag == "loadNinjaSagaSettings" || tag == "saveNinjaSagaSettings") {
                val settingsMethod =
                    if (_uiState.value.currentBaseGame?.id == "zenshin") "get_zenshin_settings"
                    else "get_ninjasaga_settings"
                val settingsResult = bridge.call(settingsMethod)
                if (settingsResult.optBoolean("success")) {
                    _uiState.value = _uiState.value.copy(
                        ninjaSagaSettings = settingsResult.optJSONObject("settings").toNinjaSagaSettingsUi(),
                    )
                }
            }
            _uiState.value = _uiState.value.copy(
                actionStateSyncing = false,
                isBusy = false,
                statusMessage = if (result.optBoolean("success")) {
                    when (tag) {
                        "login" -> {
                            if (result.optBoolean("requires_verification")) {
                                result.optString("message", "Verification code required")
                            } else {
                                updateBackgroundService(shouldRun = true)
                                refreshBillingStatus()
                                "Login success"
                            }
                        }
                        "loginNinjaSagaWebAuth" -> {
                            updateBackgroundService(shouldRun = true)
                            refreshBillingStatus()
                            "NinjaSaga web login success"
                        }
                        "quickLogin" -> {
                            if (result.optBoolean("requires_verification")) {
                                result.optString("message", "Verification code required")
                            } else {
                                updateBackgroundService(shouldRun = true)
                                refreshBillingStatus()
                                "Quick login success"
                            }
                        }
                        "verifyRiftCode" -> {
                            updateBackgroundService(shouldRun = true)
                            refreshBillingStatus()
                            "Ninja Rift verification success"
                        }
                        "saveRiftSettings" -> "Ninja Rift settings saved"
                        "selectCharacter" -> "Character selected"
                        "refreshCharacter" -> "Character refreshed"
                        "changeCharacter" -> "Choose another character"
                        "selectBaseGame" -> "Base game selected"
                        "startAction" -> "Action started"
                        "startClanWar" -> "Clan War started"
                        "stopAction" -> "Stopping action"
                        "clearLogs" -> "Logs cleared"
                        "logout" -> {
                            updateBackgroundService(shouldRun = false)
                            "Logged out"
                        }
                        else -> null
                    }
                } else {
                    result.optString("message", "Action failed")
                },
            )
            val billingSnapshot = billingRepository.snapshotNow()
            applyBillingSnapshot(billingSnapshot)
        }
    }

    private fun applyState(payload: JSONObject) {
        val previousState = _uiState.value
        val previousCaptchaRequired = lastClanWarCaptchaRequired
        val characters = payload.optJSONArray("characters").toCharacterOptions()
        val actions = payload.optJSONObject("actions").toActions()
        val incomingLogs = payload.optJSONArray("logs").toLogs()
        val payloadRunning = payload.optBoolean("running")
        val payloadRunningAction = payload.optString("running_action").takeIf { it.isNotBlank() && it != "null" }
        val logs = if (
            incomingLogs.isEmpty() &&
            previousState.logs.isNotEmpty() &&
            (previousState.running || payloadRunning || previousState.runningAction != null || payloadRunningAction != null)
        ) {
            previousState.logs
        } else {
            incomingLogs
        }
        val baseGames = payload.optJSONArray("base_games").toBaseGames()
        val currentBaseGame = payload.optJSONObject("current_base_game").toBaseGameOption()
        val currentProfile = payload.optJSONObject("current_amf_profile").toAmfProfileOption() ?: previousState.currentAmfProfile
        val effectiveBaseGame = currentBaseGame ?: previousState.currentBaseGame
        val clanWar = payload.optJSONObject("clan_war")
        val captchaRequired = clanWar?.optBoolean("captcha_required", false) == true
        val clanWarSnapshot = clanWar?.optJSONObject("snapshot")
        val currentTarget = clanWar?.optJSONObject("current_target")
        val captchaMessage = clanWar?.optString("captcha_message")?.takeIf { it.isNotBlank() && it != "null" }.orEmpty()
        val captchaDebug = clanWar?.optJSONObject("captcha_debug")
        val captchaDebugJson = captchaDebug?.toString(2)
        val loginKey = run {
            val baseId = effectiveBaseGame?.id.orEmpty()
            val profileId = currentProfile?.id.orEmpty()
            if (baseId.isBlank() || profileId.isBlank()) profileId else "${baseId}__${profileId}"
        }
        val reauthRequiredReason = payload.optString("reauth_required_reason").takeIf { it.isNotBlank() && it != "null" }
        val riftVerificationRequired = payload.optBoolean("rift_verification_required", false)
        val riftVerificationMessage = payload.optString("rift_verification_message").takeIf { it.isNotBlank() && it != "null" }.orEmpty()
        val selectedEnemies = previousState.selectedEnemies.toMutableMap()
        actions.forEach { action ->
            if (action.enemyOptions.isNotEmpty() && selectedEnemies[action.key] == null) {
                selectedEnemies[action.key] = action.enemyOptions.first().id
            }
        }
        _uiState.value = _uiState.value.copy(
            hasQuickLogin = secureCredentialsStore.hasSavedLogin(loginKey),
            baseGames = if (baseGames.isNotEmpty()) baseGames else _uiState.value.baseGames,
            currentBaseGame = effectiveBaseGame,
            characters = characters,
            character = payload.optJSONObject("character").toCharacterSummary(),
            actions = actions,
            logs = logs,
            running = payloadRunning,
            runningAction = payloadRunningAction,
            actionStateSyncing = false,
            selectedEnemies = selectedEnemies,
            currentAmfProfile = currentProfile,
            showBaseGameSelection = if (payload.optJSONObject("character").toCharacterSummary() != null || characters.isNotEmpty()) {
                false
            } else {
                _uiState.value.showBaseGameSelection
            },
            showServerSelection = if (payload.optJSONObject("character").toCharacterSummary() != null || characters.isNotEmpty()) {
                false
            } else {
                _uiState.value.showServerSelection
            },
            riftVerification = RiftVerificationUi(
                required = riftVerificationRequired,
                message = riftVerificationMessage,
            ),
            statusMessage = reauthRequiredReason?.let { "Reauthentication required: $it" } ?: previousState.statusMessage,
            clanWarCaptcha = previousState.clanWarCaptcha.copy(
                required = captchaRequired,
                message = captchaMessage,
                challengeJson = if (captchaRequired) previousState.clanWarCaptcha.challengeJson else null,
                loading = if (captchaRequired) previousState.clanWarCaptcha.loading else false,
                verifying = if (captchaRequired) previousState.clanWarCaptcha.verifying else false,
                error = if (captchaRequired) previousState.clanWarCaptcha.error else null,
                debugJson = if (captchaRequired) captchaDebugJson else null,
                submittedAnswer = if (captchaRequired) previousState.clanWarCaptcha.submittedAnswer else null,
            ),
            clanWarPanel = previousState.clanWarPanel.copy(
                running = clanWar?.optBoolean("running", false) == true,
                currentTargetId = currentTarget?.optString("id", "").orEmpty(),
                currentTargetName = currentTarget?.optString("name", "").orEmpty(),
                clan = clanWarSnapshot.optClanWarClanInfo(),
                character = clanWarSnapshot.optClanWarCharacterInfo(),
                warList = clanWarSnapshot.optClanWarWarList(),
                memberList = clanWarSnapshot.optClanWarMemberList(),
                selectedRecruiters = clanWarSnapshot.optClanWarSelectedRecruiters(),
                bleedingReputationGained = clanWarSnapshot?.optBoolean("bleeding_reputation_gained", false) == true,
            ),
        )
        lastClanWarCaptchaRequired = captchaRequired
        if (!previousCaptchaRequired && captchaRequired) {
            pendingClanWarCaptchaAlertMessage =
                clanWar?.optString("captcha_message", "")?.ifBlank { "Clan War captcha needs to be solved." }
                    ?: "Clan War captcha needs to be solved."
        }
        if (!captchaRequired) {
            pendingClanWarCaptchaAlertMessage = null
        } else {
            flushPendingClanWarCaptchaAlertIfNeeded()
        }
    }

    private fun startPolling() {
        pollJob?.cancel()
        pollJob = viewModelScope.launch(Dispatchers.IO) {
            while (true) {
                val result = bridge.call("get_state")
                if (result.optBoolean("success")) {
                    applyState(result)
                } else if (_uiState.value.statusMessage == null) {
                    _uiState.value = _uiState.value.copy(
                        statusMessage = result.optString("message", "Background refresh failed"),
                    )
                }
                billingRefreshTick += 1
                val billingSnapshot = if (billingRefreshTick % 2400 == 0) {
                    billingRepository.refresh()
                } else {
                    billingRepository.snapshotNow()
                }
                applyBillingSnapshot(billingSnapshot)
                delay(1500)
            }
        }
    }

    private fun updateBackgroundService(shouldRun: Boolean) {
        val context = getApplication<Application>().applicationContext
        if (shouldRun) {
            PanelForegroundService.start(context)
        } else {
            PanelForegroundService.stop(context)
        }
    }

    private fun flushPendingClanWarCaptchaAlertIfNeeded() {
        val pendingMessage = pendingClanWarCaptchaAlertMessage ?: return
        if (MainActivity.isVisible) return
        notifyClanWarCaptchaNeeded(pendingMessage)
        pendingClanWarCaptchaAlertMessage = null
    }

    private fun notifyClanWarCaptchaNeeded(message: String) {
        val context = getApplication<Application>().applicationContext
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                val manager = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
                val channel = NotificationChannel(
                    CAPTCHA_NOTIFICATION_CHANNEL_ID,
                    "Clan War Captcha",
                    NotificationManager.IMPORTANCE_DEFAULT,
                ).apply {
                    description = "Alerts when NinjaSaga Clan War needs captcha input"
                    enableVibration(false)
                }
                manager.createNotificationChannel(channel)
            }

            val notificationPermissionGranted =
                Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU ||
                    ContextCompat.checkSelfPermission(context, android.Manifest.permission.POST_NOTIFICATIONS) == PackageManager.PERMISSION_GRANTED

            if (notificationPermissionGranted) {
                val pendingIntent = PendingIntent.getActivity(
                    context,
                    CAPTCHA_NOTIFICATION_ID,
                    Intent(context, MainActivity::class.java).apply {
                        flags = Intent.FLAG_ACTIVITY_SINGLE_TOP or Intent.FLAG_ACTIVITY_CLEAR_TOP
                    },
                    PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
                )
                val notification = NotificationCompat.Builder(context, CAPTCHA_NOTIFICATION_CHANNEL_ID)
                    .setSmallIcon(R.mipmap.ic_launcher)
                    .setContentTitle("Clan War captcha needs attention")
                    .setContentText(message)
                    .setStyle(NotificationCompat.BigTextStyle().bigText(message))
                    .setPriority(NotificationCompat.PRIORITY_DEFAULT)
                    .setCategory(NotificationCompat.CATEGORY_STATUS)
                    .setAutoCancel(true)
                    .setContentIntent(pendingIntent)
                    .build()
                NotificationManagerCompat.from(context).notify(CAPTCHA_NOTIFICATION_ID, notification)
            }
        } catch (_: Throwable) {
        }

        try {
            val pattern = longArrayOf(0, 180, 120, 180, 120, 260)
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                val vibratorManager = context.getSystemService(Context.VIBRATOR_MANAGER_SERVICE) as? VibratorManager
                vibratorManager?.defaultVibrator?.vibrate(VibrationEffect.createWaveform(pattern, -1))
            } else {
                @Suppress("DEPRECATION")
                val vibrator = context.getSystemService(Context.VIBRATOR_SERVICE) as? Vibrator
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                    vibrator?.vibrate(VibrationEffect.createWaveform(pattern, -1))
                } else {
                    @Suppress("DEPRECATION")
                    vibrator?.vibrate(pattern, -1)
                }
            }
        } catch (_: Throwable) {
        }
    }

}

private const val CAPTCHA_NOTIFICATION_CHANNEL_ID = "nse_clan_war_captcha"
private const val CAPTCHA_NOTIFICATION_ID = 2002

private fun JSONArray?.toAmfProfiles(): List<AmfProfileOption> {
    if (this == null) return emptyList()
    val list = mutableListOf<AmfProfileOption>()
    for (i in 0 until length()) {
        val item = optJSONObject(i) ?: continue
        item.toAmfProfileOption()?.let(list::add)
    }
    return list
}

private fun JSONObject?.toAmfProfileOption(): AmfProfileOption? {
    if (this == null) return null
    val id = optString("id")
    if (id.isBlank()) return null
    return AmfProfileOption(
        id = id,
        label = optString("label", id),
        gateway = optString("gateway"),
        buildNum = optString("build_num"),
    )
}

private fun JSONArray?.toBaseGames(): List<BaseGameOption> {
    if (this == null) return emptyList()
    val list = mutableListOf<BaseGameOption>()
    for (i in 0 until length()) {
        val item = optJSONObject(i) ?: continue
        item.toBaseGameOption()?.let(list::add)
    }
    return list
}

private fun JSONObject?.toBaseGameOption(): BaseGameOption? {
    if (this == null) return null
    val id = optString("id")
    if (id.isBlank()) return null
    return BaseGameOption(
        id = id,
        label = optString("label", id),
        serverSelectionNote = optString("server_selection_note"),
    )
}

private fun JSONObject?.toNinjaSagaSettingsUi(): NinjaSagaSettingsUi {
    if (this == null) return NinjaSagaSettingsUi()
    return NinjaSagaSettingsUi(
        levelingActionDelaySeconds = optInt("leveling_action_delay_seconds", 10),
        levelingCycleCooldownSeconds = optInt("leveling_cycle_cooldown_seconds", 5),
        levelingRestEveryCycles = optInt("leveling_rest_every_cycles", 40),
        levelingRestDurationSeconds = optInt("leveling_rest_duration_seconds", 60),
        levelingActionJitterSeconds = optInt("leveling_action_jitter_seconds", 2),
        levelingMinCallDelaySeconds = optInt("leveling_min_call_delay_seconds", 4),
        levelingStartRetryDelaySeconds = optInt("leveling_start_retry_delay_seconds", 6),
        levelingStartMaxRetries = optInt("leveling_start_max_retries", 3),
        levelingCloudflareRestSeconds = optInt("leveling_cloudflare_rest_seconds", 60),
        levelingCloudflareBackoffSteps = opt("leveling_cloudflare_backoff_steps_seconds")?.let {
            when (it) {
                is JSONArray -> {
                    buildString {
                        for (i in 0 until it.length()) {
                            if (i > 0) append(",")
                            append(it.opt(i).toString())
                        }
                    }
                }
                else -> it.toString()
            }
        } ?: "60,120,240",
        levelingFailureWindowSeconds = optInt("leveling_failure_window_seconds", 180),
        levelingMaxFailuresInWindow = optInt("leveling_max_failures_in_window", 6),
        levelingCircuitCooldownSeconds = optInt("leveling_circuit_cooldown_seconds", 120),
        eudemonStartFinishDelaySeconds = optInt("eudemon_start_finish_delay_seconds", 25),
        eudemonCycleCooldownSeconds = optInt("eudemon_cycle_cooldown_seconds", 5),
        easterBattleDelaySeconds = optInt("easter_battle_delay_seconds", 25),
        easterCycleCooldownSeconds = optInt("easter_cycle_cooldown_seconds", 5),
        sakuraBattleDelaySeconds = optInt("sakura_battle_delay_seconds", 20),
        easterAutoSpendEnabled = optBoolean("easter_auto_spend_enabled", false),
        easterAutoSpendMaxRefillsPerRun = optInt("easter_auto_spend_max_refills_per_run", 0),
        easterAutoSpendBuyAmount = optInt("easter_auto_spend_buy_amount", 3),
        eventResourceMode = optString("event_resource_mode", "stop"),
        eventWaitMinutes = optInt("event_wait_minutes", 30),
        specialJouninClassIndex = optInt("special_jounin_class_index", 3).coerceIn(1, 5),
        tpTrainingAbuseLoop = optInt("tp_training_abuse_loop", 1).coerceAtLeast(1),
        ssTrainingAbuseLoop = optInt("ss_training_abuse_loop", 1).coerceAtLeast(1),
        clanWarAutoSpendToken = optBoolean("clan_war_auto_spend_token", false),
        clanWarStaminaRefillSource = optString("clan_war_stamina_refill_source", "auto").ifBlank { "auto" },
        clanWarBleedingMode = optBoolean("clan_war_bleeding_mode", false),
        clanWarManualRecruit = optBoolean("clan_war_manual_recruit", false),
        clanWarManualMemberIds = opt("clan_war_manual_member_ids")?.let {
            when (it) {
                is JSONArray -> buildString {
                    for (i in 0 until it.length()) {
                        val value = it.opt(i)?.toString()?.trim().orEmpty()
                        if (value.isNotBlank()) {
                            if (isNotEmpty()) append(",")
                            append(value)
                        }
                    }
                }
                else -> it.toString()
            }
        } ?: "",
        clanWarTargetClanId = optString("clan_war_target_clan_id", ""),
        clanWarTargetClanName = optString("clan_war_target_clan_name", ""),
        clanWarBattleDelaySeconds = optInt("clan_war_battle_delay_seconds", 8),
        clanWarRefreshDelaySeconds = optInt("clan_war_refresh_delay_seconds", 4),
        clanWarBuyStaminaDelaySeconds = optInt("clan_war_buy_stamina_delay_seconds", 3),
        clanWarAmfCallDelaySeconds = optInt("clan_war_amf_call_delay_seconds", 1),
        clanWarPostCaptchaResumeDelaySeconds = optInt("clan_war_post_captcha_resume_delay_seconds", 1),
        clanWarLowStaminaWaitMinutes = optInt("clan_war_low_stamina_wait_minutes", 30),
    )
}

private fun JSONObject?.optClanWarClanInfo(): ClanWarClanInfoUi {
    val clan = this?.optJSONObject("clan")
    return ClanWarClanInfoUi(
        id = clan?.opt("id")?.toString().orEmpty(),
        name = clan?.optString("name", "Unknown Clan") ?: "Unknown Clan",
        reputation = clan?.optInt("reputation", 0) ?: 0,
    )
}

private fun JSONObject?.optClanWarCharacterInfo(): ClanWarCharacterInfoUi {
    val char = this?.optJSONObject("char")
    return ClanWarCharacterInfoUi(
        stamina = char?.optInt("stamina", 0) ?: 0,
        maxStamina = char?.optInt("max_stamina", 0) ?: 0,
        prestige = char?.opt("prestige")?.toString() ?: "n/a",
    )
}

private fun JSONObject?.optClanWarWarList(): List<ClanWarWarItemUi> {
    val array = this?.optJSONArray("war_list") ?: return emptyList()
    val list = mutableListOf<ClanWarWarItemUi>()
    for (i in 0 until array.length()) {
        val item = array.optJSONObject(i) ?: continue
        list += ClanWarWarItemUi(
            id = item.opt("id")?.toString().orEmpty(),
            name = item.optString("name", "Unknown Clan"),
            reputation = item.opt("reputation")?.toString() ?: "0",
            master = item.opt("master")?.toString() ?: "-",
            members = item.opt("members")?.toString() ?: "?",
        )
    }
    return list
}

private fun JSONObject?.optClanWarMemberList(): List<ClanWarMemberUi> {
    val array = this?.optJSONArray("member_list") ?: return emptyList()
    val list = mutableListOf<ClanWarMemberUi>()
    for (i in 0 until array.length()) {
        val item = array.optJSONObject(i) ?: continue
        list += ClanWarMemberUi(
            id = item.opt("id")?.toString().orEmpty(),
            name = item.optString("name", "Unknown"),
            level = item.optInt("level", 0),
            stamina = item.optInt("stamina", 0),
            reputationGain = item.optInt("reputation_gain", 0),
        )
    }
    return list
}

private fun JSONObject?.optClanWarSelectedRecruiters(): List<String> {
    val array = this?.optJSONArray("selected_recruiters") ?: return emptyList()
    val list = mutableListOf<String>()
    for (i in 0 until array.length()) {
        val value = array.opt(i)?.toString()?.trim().orEmpty()
        if (value.isNotBlank()) list += value
    }
    return list
}

private fun JSONObject?.toSageSettingsUi(): SageSettingsUi {
    if (this == null) return SageSettingsUi()
    return SageSettingsUi(
        generalActionDelaySeconds = optInt("leveling_delay_seconds", 10),
        cycleCooldownSeconds = optInt("leveling_cycle_cooldown_seconds", 5),
        restEveryCycles = optInt("leveling_rest_every_cycles", 40),
        restDurationSeconds = optInt("leveling_rest_duration_seconds", 60),
        actionJitterSeconds = optInt("leveling_action_jitter_seconds", 2),
        minCallDelaySeconds = optInt("leveling_min_call_delay_seconds", 4),
        startRetryDelaySeconds = optInt("leveling_start_retry_delay_seconds", 6),
        startMaxRetries = optInt("leveling_start_max_retries", 3),
        failureWindowSeconds = optInt("leveling_failure_window_seconds", 180),
        maxFailuresInWindow = optInt("leveling_max_failures_in_window", 6),
        circuitCooldownSeconds = optInt("leveling_circuit_cooldown_seconds", 120),
        examStartDelaySeconds = optInt("sage_exam_start_delay_seconds", 8),
        examFinishDelaySeconds = optInt("sage_exam_finish_delay_seconds", 5),
        battleDurationDelaySeconds = optInt("sage_battle_wait_seconds", 5),
        afterFinishDelaySeconds = optInt("sage_post_finish_delay_seconds", 0),
        autoReloginWaitSeconds = optInt("sage_auto_relogin_wait_seconds", 20),
        infiniteLoopRestEveryMissions = optInt("sage_infinite_loop_rest_every_cycles", 50),
        infiniteLoopRestDurationSeconds = optInt("sage_infinite_loop_rest_duration_seconds", 10),
        limitedLoopRestEveryMissions = optInt("sage_limited_loop_rest_every_cycles", 15),
        limitedLoopRestDurationSeconds = optInt("sage_limited_loop_rest_duration_seconds", 10),
        specialJouninClassSkill = optString("sage_special_jounin_class_skill", "skill_4001"),
        eventResourceMode = optString("sage_event_empty_resource_mode", "stop"),
        eventWaitMinutes = optInt("sage_event_wait_minutes", 30),
        anivEventResourceMode = optString("sage_aniv_event_empty_resource_mode", "stop"),
        anivEventWaitMinutes = optInt("sage_aniv_event_wait_minutes", 30),
        sakuraEventResourceMode = optString("sage_sakura_event_empty_resource_mode", "stop"),
        sakuraEventWaitMinutes = optInt("sage_sakura_event_wait_minutes", 30),
        easterEventResourceMode = optString("sage_easter_event_empty_resource_mode", "stop"),
        easterEventWaitMinutes = optInt("sage_easter_event_wait_minutes", 30),
        shadowWarResourceMode = optString("sage_shadow_war_empty_resource_mode", "stop"),
        shadowWarWaitMinutes = optInt("sage_shadow_war_wait_minutes", 30),
        clanWarAutoSpendToken = optBoolean("clan_war_auto_spend_token", false),
        clanWarStaminaRefillSource = optString("clan_war_stamina_refill_source", "auto").ifBlank { "auto" },
        clanWarBattleDelaySeconds = optInt("clan_war_battle_delay_seconds", 8),
        clanWarBuyStaminaDelaySeconds = optInt("clan_war_buy_stamina_delay_seconds", 3),
    )
}

private fun JSONArray?.toRiftSkillOptions(): List<RiftSkillOption> {
    if (this == null) return emptyList()
    val list = mutableListOf<RiftSkillOption>()
    for (i in 0 until length()) {
        val item = optJSONObject(i) ?: continue
        val id = item.optString("id")
        if (id.isBlank()) continue
        list += RiftSkillOption(
            id = id,
            label = item.optString("label", id),
        )
    }
    return list
}

private fun JSONObject?.toRiftSettingsUi(): RiftSettingsUi {
    if (this == null) return RiftSettingsUi()
    return RiftSettingsUi(
        minCallDelaySeconds = optInt("rift_min_call_delay_seconds", 2),
        loopDelaySeconds = optInt("rift_loop_delay_seconds", 1),
        autoReloginWaitSeconds = optInt("rift_auto_relogin_wait_seconds", 15),
        infiniteLoopRestEveryCycles = optInt("rift_infinite_loop_rest_every_cycles", 40),
        infiniteLoopRestDurationSeconds = optInt("rift_infinite_loop_rest_duration_seconds", 30),
        limitedLoopRestEveryCycles = optInt("rift_limited_loop_rest_every_cycles", 15),
        limitedLoopRestDurationSeconds = optInt("rift_limited_loop_rest_duration_seconds", 15),
        missionBattleWaitBaseSeconds = optInt("rift_mission_battle_wait_base_seconds", 20),
        missionBattleWaitRandomSeconds = optInt("rift_mission_battle_wait_random_seconds", 20),
        eventBattleWaitBaseSeconds = optInt("rift_event_battle_wait_base_seconds", 20),
        eventBattleWaitRandomSeconds = optInt("rift_event_battle_wait_random_seconds", 20),
        eudemonBattleWaitBaseSeconds = optInt("rift_eudemon_battle_wait_base_seconds", 20),
        eudemonBattleWaitRandomSeconds = optInt("rift_eudemon_battle_wait_random_seconds", 5),
        eudemonBetweenBattlesDelaySeconds = optInt("rift_eudemon_between_battles_delay_seconds", 5),
        huntingHouseBattleWaitBaseSeconds = optInt("rift_hunting_house_battle_wait_base_seconds", 20),
        huntingHouseBattleWaitRandomSeconds = optInt("rift_hunting_house_battle_wait_random_seconds", 5),
        huntingHouseBetweenBattlesDelaySeconds = optInt("rift_hunting_house_between_battles_delay_seconds", 5),
        examWaitMinSeconds = optInt("rift_exam_wait_min_seconds", 45),
        examWaitMaxSeconds = optInt("rift_exam_wait_max_seconds", 120),
        examStageGapSeconds = optInt("rift_exam_stage_gap_seconds", 3),
        specialJouninClassSkill = optString("rift_special_jounin_class_skill", "skill_2001"),
        eventResourceMode = optString("rift_event_empty_resource_mode", "stop"),
        eventWaitMinutes = optInt("rift_event_wait_minutes", 30),
        hanamiEventResourceMode = optString("rift_hanami_event_empty_resource_mode", "stop"),
        hanamiEventWaitMinutes = optInt("rift_hanami_event_wait_minutes", 30),
        easterEventResourceMode = optString("rift_easter_event_empty_resource_mode", "stop"),
        easterEventWaitMinutes = optInt("rift_easter_event_wait_minutes", 30),
    )
}

private fun JSONArray?.toCharacterOptions(): List<CharacterOption> {
    if (this == null) return emptyList()
    val list = mutableListOf<CharacterOption>()
    for (i in 0 until length()) {
        val item = optJSONObject(i) ?: continue
        list += CharacterOption(
            index = item.optInt("index"),
            id = item.optString("character_id"),
            name = item.optString("character_name"),
            level = item.optInt("character_level"),
        )
    }
    return list
}

private fun JSONObject?.toCharacterSummary(): CharacterSummary? {
    if (this == null) return null
    return CharacterSummary(
        name = optString("name"),
        level = optInt("level"),
        xp = optInt("xp"),
        gold = optInt("gold"),
        tokens = optInt("tokens"),
        characterId = optString("character_id"),
    )
}

private fun JSONArray?.toLogs(): List<LogEntry> {
    if (this == null) return emptyList()
    val list = mutableListOf<LogEntry>()
    for (i in 0 until length()) {
        val item = optJSONObject(i) ?: continue
        list += LogEntry(
            message = item.optString("message"),
            level = item.optString("level", "info"),
        )
    }
    return list
}

private fun JSONObject?.toActions(): List<ActionUi> {
    if (this == null) return emptyList()
    val hiddenActions = setOf(
        "cd_event",
        "phantom",
        "pumpkin_event",
        "snow_event",
        "thanks_event",
        "yinyang_event",
    )
    val keys = keys()
    val list = mutableListOf<ActionUi>()
    while (keys.hasNext()) {
        val key = keys.next()
        if (key in hiddenActions) continue
        val value = optJSONObject(key) ?: continue
        val enemyOptionsJson = value.optJSONArray("enemy_options")
        val enemyOptions = mutableListOf<EnemyOption>()
        if (enemyOptionsJson != null) {
            for (i in 0 until enemyOptionsJson.length()) {
                val item = enemyOptionsJson.optJSONObject(i) ?: continue
                enemyOptions += EnemyOption(
                    id = item.optString("id"),
                    name = item.optString("name"),
                )
            }
        }
        list += ActionUi(
            key = key,
            label = value.optString("label", key),
            enemyOptions = enemyOptions,
        )
    }
    val pinnedOrder = listOf("leveling", "eudemon", "monster_hunt")
    val bottomOrder = listOf("sakura_event")
    return list.sortedWith(
        compareBy<ActionUi> { pinnedOrder.indexOf(it.key).let { idx -> if (idx == -1) Int.MAX_VALUE else idx } }
            .thenBy { it.key in bottomOrder }
            .thenBy { it.label },
    )
}
