package com.ninjasage.android

import android.content.Context
import com.chaquo.python.PyObject
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import com.theforgotten.nsepanel.BuildConfig
import org.json.JSONObject

class PythonBridge(context: Context) {
    private val appContext = context.applicationContext
    private var startupError: String? = null

    init {
        try {
            if (!Python.isStarted()) {
                Python.start(AndroidPlatform(appContext))
            }
        } catch (e: Throwable) {
            startupError = e.stackTraceToString()
        }
    }

    private val module: PyObject by lazy {
        Python.getInstance().getModule("ninja_sage_android.bridge")
    }

    init {
        if (startupError == null) {
            val result = call("initialize", appContext.filesDir.absolutePath, BuildConfig.DISABLE_REMOTE_SAVE)
            if (!result.optBoolean("success")) {
                startupError = result.optString("message", "Python initialization failed")
            }
        }
    }

    fun call(method: String, vararg args: Any?): JSONObject {
        val error = startupError
        if (error != null) {
            return JSONObject()
                .put("success", false)
                .put("message", error)
        }

        return try {
            val result = module.callAttr(method, *args).toString()
            JSONObject(result)
        } catch (e: Throwable) {
            JSONObject()
                .put("success", false)
                .put("message", e.stackTraceToString())
        }
    }
}
