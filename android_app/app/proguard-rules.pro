# Keep Chaquopy entry points reachable while allowing app code obfuscation.
-keep class com.chaquo.python.** { *; }
-keep class org.python.** { *; }
-keep class com.ninjasage.android.PythonBridge { *; }

# Keep native method names stable if Android/python bridge needs them.
-keepclasseswithmembernames class * {
    native <methods>;
}

# Start.io SDK keep rules from official integration docs.
-keep class com.startapp.** { *; }
-keep class com.truenet.** { *; }
-keepattributes Exceptions, InnerClasses, Signature, Deprecated, SourceFile, LineNumberTable, *Annotation*, EnclosingMethod
-dontwarn android.webkit.JavascriptInterface
-dontwarn com.startapp.**
-dontwarn org.jetbrains.annotations.**

# LevelPlay / Unity mediation release rules.
-keepclassmembers class * implements android.os.Parcelable {
    public static final android.os.Parcelable$Creator *;
}
-keep class com.google.android.gms.ads.** { public *; }
-keep class com.google.android.gms.appset.** { *; }
-keep class com.google.android.gms.tasks.** { *; }
-keep class com.ironsource.adapters.** { *; }
-keepclassmembers class com.ironsource.** { public *; }
-keep public class com.ironsource.**
-keep class com.iab.omid.** { *; }
-keepattributes JavascriptInterface
-keepclassmembers class * {
    @android.webkit.JavascriptInterface <methods>;
}
-dontwarn com.ironsource.**
-dontwarn com.ironsource.adapters.**
-dontwarn com.iab.omid.**

# Strip noisy logs from release builds where possible.
-assumenosideeffects class android.util.Log {
    public static int v(...);
    public static int d(...);
    public static int i(...);
}
