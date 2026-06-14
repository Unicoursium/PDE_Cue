package com.example.cue.ui.theme

import androidx.compose.material3.Typography as MaterialTypography
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.Font
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.sp
import com.example.cue.R

val KoulenFontFamily = FontFamily(
    Font(
        resId = R.font.koulen_regular,
        weight = FontWeight.Normal
    )
)

val InterFontFamily = FontFamily(
    Font(
        resId = R.font.inter_light,
        weight = FontWeight.Light
    )
)

private fun MaterialTypography.withCueFonts(): MaterialTypography {
    return copy(
        displayLarge = displayLarge.copy(fontFamily = KoulenFontFamily),
        displayMedium = displayMedium.copy(fontFamily = KoulenFontFamily),
        displaySmall = displaySmall.copy(fontFamily = KoulenFontFamily),
        headlineLarge = headlineLarge.copy(fontFamily = KoulenFontFamily),
        headlineMedium = headlineMedium.copy(fontFamily = KoulenFontFamily),
        headlineSmall = headlineSmall.copy(fontFamily = KoulenFontFamily),
        titleLarge = titleLarge.copy(fontFamily = KoulenFontFamily),
        titleMedium = titleMedium.copy(fontFamily = KoulenFontFamily),
        titleSmall = titleSmall.copy(fontFamily = KoulenFontFamily),
        bodyLarge = bodyLarge.copy(fontFamily = InterFontFamily),
        bodyMedium = bodyMedium.copy(fontFamily = InterFontFamily),
        bodySmall = bodySmall.copy(fontFamily = InterFontFamily),
        labelLarge = labelLarge.copy(fontFamily = InterFontFamily),
        labelMedium = labelMedium.copy(fontFamily = InterFontFamily),
        labelSmall = labelSmall.copy(fontFamily = InterFontFamily)
    )
}

val Typography = MaterialTypography().withCueFonts().copy(
    bodyLarge = TextStyle(
        fontFamily = InterFontFamily,
        fontWeight = FontWeight.Light,
        fontSize = 16.sp,
        lineHeight = 24.sp,
        letterSpacing = 0.sp
    )
)
