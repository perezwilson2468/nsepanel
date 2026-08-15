package com.randomideax.nsepanel

import android.app.Activity
import android.os.Bundle
import android.widget.TextView

class EmptyPackageActivity : Activity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        val label = TextView(this).apply {
            text = "Empty verification package for com.randomideax.nsepanel"
            setPadding(48, 48, 48, 48)
        }

        setContentView(label)
    }
}
