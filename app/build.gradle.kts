plugins {
    id("com.android.application")
}

android {
    namespace = "com.varoxan.voxbook"
    compileSdk = 36

    defaultConfig {
        applicationId = "com.varoxan.voxbook"
        minSdk = 26
        targetSdk = 36
        versionCode = 1
        versionName = "0.1.0"
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
}

dependencies {
    implementation("com.tom-roush:pdfbox-android:2.0.27.0")
}
