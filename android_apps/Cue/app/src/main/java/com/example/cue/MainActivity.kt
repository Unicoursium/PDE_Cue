package com.example.cue

import android.nfc.NfcAdapter
import android.nfc.NdefMessage
import android.nfc.NdefRecord
import android.nfc.Tag
import android.nfc.tech.Ndef
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.scale
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.google.firebase.Timestamp
import com.google.firebase.firestore.FieldValue
import com.google.firebase.firestore.FirebaseFirestore
import kotlinx.coroutines.delay
import java.nio.charset.Charset


private val AccentPink = Color(0xFFB52E62)
private val SoftPink = Color(0xFFF9D8E4)
private val PaperWhite = Color(0xFFFFFCF8)
private val InkBlack = Color(0xFF161616)
private val MutedGrey = Color(0xFF6E6E6E)

class MainActivity : ComponentActivity(), NfcAdapter.ReaderCallback {

    private var nfcAdapter: NfcAdapter? = null
    private val firestore by lazy {
        FirebaseFirestore.getInstance()
    }

    private var currentScreen by mutableStateOf<AppScreen>(AppScreen.Scan)
    private var scannedWristbandId by mutableStateOf("")
    private var scannedRfidEpc by mutableStateOf("")
    private var scanError by mutableStateOf<String?>(null)
    private var profileSaveInProgress by mutableStateOf(false)
    private var profileSaveStatus by mutableStateOf<String?>(null)

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        nfcAdapter = NfcAdapter.getDefaultAdapter(this)

        scanError = when {
            nfcAdapter == null -> {
                "This phone does not support NFC."
            }

            nfcAdapter?.isEnabled == false -> {
                "Please enable NFC in your phone settings."
            }

            else -> {
                null
            }
        }

        setContent {
            MaterialTheme {
                CueApp(
                    screen = currentScreen,
                    wristbandId = scannedWristbandId,
                    scanError = scanError,
                    profileSaveInProgress = profileSaveInProgress,
                    profileSaveStatus = profileSaveStatus,
                    onScanAgain = {
                        scannedWristbandId = ""
                        scannedRfidEpc = ""
                        scanError = null
                        profileSaveInProgress = false
                        profileSaveStatus = null
                        currentScreen = AppScreen.Scan
                    },
                    onProfileSaved = { name, age, gender, lookingFor ->
                        saveProfile(
                            nfcUid = scannedWristbandId,
                            rfidEpc = scannedRfidEpc,
                            name = name,
                            age = age,
                            gender = gender,
                            lookingFor = lookingFor
                        )
                    },
                    onPersonalityActivated = { selectedPersonality ->
                        activatePersonality(selectedPersonality)
                    },
                    onCloseApp = {
                        finishAndRemoveTask()
                    }
                )
            }
        }
    }

    override fun onResume() {
        super.onResume()
        enableNfcReaderMode()
    }

    override fun onPause() {
        super.onPause()
        nfcAdapter?.disableReaderMode(this)
    }

    private fun enableNfcReaderMode() {
        val adapter = nfcAdapter ?: return

        if (!adapter.isEnabled) {
            scanError = "Please enable NFC in your phone settings."
            return
        }

        val flags =
            NfcAdapter.FLAG_READER_NFC_A or
                    NfcAdapter.FLAG_READER_NFC_B or
                    NfcAdapter.FLAG_READER_NFC_F or
                    NfcAdapter.FLAG_READER_NFC_V

        adapter.enableReaderMode(
            this,
            this,
            flags,
            null
        )
    }

    override fun onTagDiscovered(tag: Tag) {
        val uid = tag.id.toHexString()
        val rfidEpc = tag.readNdefValue().orEmpty().toRfidEpc()

        runOnUiThread {
            scannedWristbandId = uid
            scannedRfidEpc = rfidEpc
            scanError = null
            profileSaveInProgress = false
            profileSaveStatus = null
            currentScreen = AppScreen.ProfileSetup
        }
    }

    private fun saveProfile(
        nfcUid: String,
        rfidEpc: String,
        name: String,
        age: String,
        gender: Gender,
        lookingFor: LookingFor
    ) {
        if (nfcUid.isBlank()) {
            profileSaveStatus = "Scan a wristband before saving."
            return
        }

        profileSaveInProgress = true
        profileSaveStatus = "Saving profile..."

        val userId = nfcUid
        val wristbandName = nfcUid.toWristbandDisplayName()
        val profile = mapOf(
            "userId" to userId,
            "name" to name,
            "nickname" to name,
            "age" to (age.toIntOrNull() ?: 0),
            "gender" to gender.name,
            "lookingFor" to lookingFor.name,
            "personality" to "",
            "status" to "INACTIVE",
            "nfcUid" to nfcUid,
            "rfidEpc" to rfidEpc,
            "wristbandName" to wristbandName,
            "wristband" to mapOf(
                "nfcUid" to nfcUid,
                "rfidEpc" to rfidEpc,
                "displayName" to wristbandName
            ),
            "createdAt" to Timestamp.now(),
            "updatedAt" to FieldValue.serverTimestamp()
        )

        firestore
            .collection("profiles")
            .document(nfcUid)
            .set(profile)
            .addOnSuccessListener {
                profileSaveInProgress = false
                profileSaveStatus = null
                currentScreen = AppScreen.PersonalitySelector
            }
            .addOnFailureListener {
                profileSaveInProgress = false
                profileSaveStatus = "Could not save profile. Check connection and try again."
            }
    }

    private fun activatePersonality(
        selectedPersonality: PersonalityType
    ) {
        val nfcUid = scannedWristbandId

        if (nfcUid.isBlank()) {
            return
        }

        firestore
            .collection("profiles")
            .document(nfcUid)
            .update(
                mapOf(
                    "personality" to selectedPersonality.name,
                    "status" to "ACTIVE",
                    "updatedAt" to FieldValue.serverTimestamp()
                )
            )
            .addOnSuccessListener {
                currentScreen = AppScreen.Activated
            }
    }
}

private sealed class AppScreen {
    data object Scan : AppScreen()
    data object ProfileSetup : AppScreen()
    data object PersonalitySelector : AppScreen()
    data object Activated : AppScreen()
}



private fun ByteArray.toHexString(): String {
    return joinToString(separator = "") { byte ->
        "%02X".format(byte)
    }
}

private fun String.toWristbandDisplayName(): String {
    return "WB-${takeLast(4).uppercase()}"
}

private fun String.toRfidEpc(): String {
    return trim()
        .replace(" ", "")
        .replace("-", "")
        .replace(":", "")
        .replace("=", "")
        .uppercase()
        .removePrefix("RFID")
        .removePrefix("UHF")
        .removePrefix("EPC")
}

private fun Tag.readNdefValue(): String? {
    val ndef = Ndef.get(this) ?: return null

    return try {
        ndef.connect()
        ndef.cachedNdefMessage?.firstReadableRecordText()
    } catch (_: Exception) {
        null
    } finally {
        try {
            ndef.close()
        } catch (_: Exception) {
            // Nothing to recover here; the tag read either succeeded or failed above.
        }
    }
}

private fun NdefMessage.firstReadableRecordText(): String? {
    return records.firstNotNullOfOrNull { record ->
        record.toReadableText()
    }
}

private fun NdefRecord.toReadableText(): String? {
    return when {
        tnf == NdefRecord.TNF_WELL_KNOWN &&
                type.contentEquals(NdefRecord.RTD_TEXT) -> {
            parseTextRecordPayload(payload)
        }

        tnf == NdefRecord.TNF_WELL_KNOWN &&
                type.contentEquals(NdefRecord.RTD_URI) -> {
            parseUriRecordPayload(payload)
        }

        else -> {
            payload.toString(Charsets.UTF_8).takeIf {
                it.isNotBlank()
            }
        }
    }
}

private fun parseTextRecordPayload(payload: ByteArray): String? {
    if (payload.isEmpty()) {
        return null
    }

    val status = payload[0].toInt()
    val languageCodeLength = status and 0x3F
    val textEncoding = if ((status and 0x80) == 0) {
        Charsets.UTF_8
    } else {
        Charset.forName("UTF-16")
    }
    val textStart = 1 + languageCodeLength

    if (payload.size <= textStart) {
        return null
    }

    return payload
        .copyOfRange(textStart, payload.size)
        .toString(textEncoding)
        .takeIf {
            it.isNotBlank()
        }
}

private fun parseUriRecordPayload(payload: ByteArray): String? {
    if (payload.isEmpty()) {
        return null
    }

    val prefixes = arrayOf(
        "",
        "http://www.",
        "https://www.",
        "http://",
        "https://"
    )
    val prefix = prefixes.getOrElse(payload[0].toInt()) {
        ""
    }
    val body = payload
        .copyOfRange(1, payload.size)
        .toString(Charsets.UTF_8)

    return "$prefix$body".takeIf {
        it.isNotBlank()
    }
}

@Composable
private fun CueApp(
    screen: AppScreen,
    wristbandId: String,
    scanError: String?,
    profileSaveInProgress: Boolean,
    profileSaveStatus: String?,
    onScanAgain: () -> Unit,
    onProfileSaved: (
        name: String,
        age: String,
        gender: Gender,
        lookingFor: LookingFor
    ) -> Unit,
    onPersonalityActivated: (
        selectedPersonality: PersonalityType
    ) -> Unit,
    onCloseApp: () -> Unit
) {
    Scaffold(
        containerColor = PaperWhite
    ) { innerPadding ->
        Box(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding)
        ) {
            when (screen) {
                AppScreen.Scan -> {
                    WristbandScanScreen(
                        scanError = scanError
                    )
                }

                AppScreen.ProfileSetup -> {
                    ProfileSetupScreen(
                        wristbandId = wristbandId,
                        isSaving = profileSaveInProgress,
                        saveStatus = profileSaveStatus,
                        onScanAgain = onScanAgain,
                        onSave = onProfileSaved
                    )
                }

                AppScreen.PersonalitySelector -> {
                    PersonalitySelectorScreen(
                        onActivate = onPersonalityActivated
                    )
                }

                AppScreen.Activated -> {
                    ActivatedScreen(
                        wristbandId = wristbandId,
                        onCloseApp = onCloseApp
                    )
                }
            }
        }
    }
}

@Composable
private fun CueLogoHeader(
    modifier: Modifier = Modifier
) {
    Image(
        painter = painterResource(id = R.drawable.cue_logo),
        contentDescription = "Cue logo",
        modifier = modifier,
        contentScale = ContentScale.Fit
    )
}

@Composable
private fun SingleLineText(
    text: String,
    modifier: Modifier = Modifier,
    color: Color,
    maxFontSize: androidx.compose.ui.unit.TextUnit,
    minFontSize: androidx.compose.ui.unit.TextUnit = 4.sp,
    fontWeight: FontWeight = FontWeight.Normal,
    textAlign: TextAlign = TextAlign.Center,
    widthFactor: Float = 0.58f,
    letterSpacing: androidx.compose.ui.unit.TextUnit = 0.sp
) {
    BoxWithConstraints(
        modifier = modifier
    ) {
        var fittedSize by remember(
            text,
            maxFontSize,
            minFontSize,
            maxWidth
        ) {
            mutableStateOf(maxFontSize)
        }

        Text(
            text = text,
            modifier = Modifier.fillMaxWidth(),
            color = color,
            fontSize = fittedSize,
            fontWeight = fontWeight,
            textAlign = textAlign,
            letterSpacing = letterSpacing,
            maxLines = 1,
            softWrap = false,
            onTextLayout = { textLayoutResult ->
                if (
                    textLayoutResult.didOverflowWidth &&
                    fittedSize.value > minFontSize.value
                ) {
                    fittedSize = (
                        fittedSize.value * 0.82f
                    ).coerceAtLeast(
                        minFontSize.value
                    ).sp
                }
            }
        )
    }
}

@Composable
private fun WristbandScanScreen(
    scanError: String?
) {
    BoxWithConstraints(
        modifier = Modifier
            .fillMaxSize()
    ) {
        val tight = maxHeight < 700.dp
        val compact = maxHeight < 760.dp
        val logoHeight = if (tight) {
            30.dp
        } else {
            38.dp
        }
        val graphicSize = if (tight) {
            174.dp
        } else if (compact) {
            198.dp
        } else {
            220.dp
        }
        val titleSize = if (tight) {
            27.sp
        } else {
            31.sp
        }

        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(
                    horizontal = 28.dp,
                    vertical = if (tight) 24.dp else 36.dp
                ),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            CueLogoHeader(
                modifier = Modifier
                    .height(logoHeight)
                    .fillMaxWidth(0.30f)
            )

            Spacer(modifier = Modifier.height(if (tight) 10.dp else 15.dp))

            SingleLineText(
                text = "WRISTBAND SCAN",
                modifier = Modifier.fillMaxWidth(),
                color = InkBlack,
                maxFontSize = titleSize,
                fontWeight = FontWeight.Black,
                textAlign = TextAlign.Center,
                widthFactor = 0.62f
            )

            Spacer(modifier = Modifier.height(6.dp))

            Box(
                modifier = Modifier
                    .width(145.dp)
                    .height(4.dp)
                    .background(
                        color = AccentPink,
                        shape = RoundedCornerShape(50)
                    )
            )

            Spacer(modifier = Modifier.height(if (tight) 16.dp else 23.dp))

            SingleLineText(
                text = "TAP YOUR NFC WRISTBAND TO START",
                modifier = Modifier.fillMaxWidth(),
                color = InkBlack,
                maxFontSize = if (tight) 17.sp else 19.sp,
                fontWeight = FontWeight.Bold,
                textAlign = TextAlign.Center,
                widthFactor = 0.58f
            )

            Spacer(modifier = Modifier.height(if (tight) 17.dp else 25.dp))

            PulsingNfcGraphic(
                graphicSize = graphicSize
            )

            Spacer(modifier = Modifier.height(if (tight) 18.dp else 25.dp))

            SingleLineText(
                text = "Hold the wristband near the top of your phone",
                modifier = Modifier.fillMaxWidth(),
                color = InkBlack,
                maxFontSize = if (tight) 16.sp else 18.sp,
                fontWeight = FontWeight.Medium,
                textAlign = TextAlign.Center,
                widthFactor = 0.52f
            )

            Spacer(modifier = Modifier.height(8.dp))

            Box(
                modifier = Modifier
                    .width(150.dp)
                    .height(4.dp)
                    .background(
                        color = AccentPink,
                        shape = RoundedCornerShape(50)
                    )
            )

            Spacer(modifier = Modifier.weight(1f))

            if (scanError == null) {
                LoadingDots()

                Spacer(modifier = Modifier.height(if (tight) 9.dp else 12.dp))

                SingleLineText(
                    text = "Waiting for wristband...",
                    modifier = Modifier.fillMaxWidth(),
                    color = InkBlack,
                    maxFontSize = if (tight) 16.sp else 18.sp,
                    fontWeight = FontWeight.Medium
                )
            } else {
                SingleLineText(
                    text = scanError,
                    modifier = Modifier.fillMaxWidth(),
                    color = AccentPink,
                    maxFontSize = 16.sp,
                    fontWeight = FontWeight.Bold,
                    textAlign = TextAlign.Center
                )
            }
        }
    }
}

@Composable
private fun PulsingNfcGraphic(
    graphicSize: androidx.compose.ui.unit.Dp = 230.dp
) {
    val transition = rememberInfiniteTransition(
        label = "nfcPulse"
    )

    val pulseScale by transition.animateFloat(
        initialValue = 0.92f,
        targetValue = 1.08f,
        animationSpec = infiniteRepeatable(
            animation = tween(
                durationMillis = 900
            ),
            repeatMode = RepeatMode.Reverse
        ),
        label = "pulseScale"
    )

    val pulseAlpha by transition.animateFloat(
        initialValue = 0.45f,
        targetValue = 1f,
        animationSpec = infiniteRepeatable(
            animation = tween(
                durationMillis = 900
            ),
            repeatMode = RepeatMode.Reverse
        ),
        label = "pulseAlpha"
    )

    Box(
        modifier = Modifier
            .size(graphicSize)
            .scale(pulseScale)
            .alpha(pulseAlpha),
        contentAlignment = Alignment.Center
    ) {
        Canvas(
            modifier = Modifier.fillMaxSize()
        ) {
            val center = Offset(
                x = size.width / 2f,
                y = size.height / 2f
            )

            drawCircle(
                color = SoftPink,
                radius = size.minDimension * 0.40f,
                center = center
            )

            drawCircle(
                color = AccentPink,
                radius = size.minDimension * 0.28f,
                center = center,
                style = Stroke(
                    width = 7f
                )
            )

            drawArc(
                color = AccentPink,
                startAngle = 210f,
                sweepAngle = 120f,
                useCenter = false,
                topLeft = Offset(
                    x = size.width * 0.23f,
                    y = size.height * 0.22f
                ),
                size = Size(
                    width = size.width * 0.54f,
                    height = size.height * 0.54f
                ),
                style = Stroke(
                    width = 8f,
                    cap = StrokeCap.Round
                )
            )

            drawArc(
                color = AccentPink,
                startAngle = 210f,
                sweepAngle = 120f,
                useCenter = false,
                topLeft = Offset(
                    x = size.width * 0.14f,
                    y = size.height * 0.13f
                ),
                size = Size(
                    width = size.width * 0.72f,
                    height = size.height * 0.72f
                ),
                style = Stroke(
                    width = 8f,
                    cap = StrokeCap.Round
                )
            )
        }

        Text(
            text = "NFC",
            color = InkBlack,
            fontSize = 30.sp,
            fontWeight = FontWeight.Black
        )
    }
}

@Composable
private fun LoadingDots() {
    val transition = rememberInfiniteTransition(
        label = "loadingDots"
    )

    val dotScale by transition.animateFloat(
        initialValue = 0.75f,
        targetValue = 1.30f,
        animationSpec = infiniteRepeatable(
            animation = tween(
                durationMillis = 600
            ),
            repeatMode = RepeatMode.Reverse
        ),
        label = "dotScale"
    )

    Row(
        horizontalArrangement = Arrangement.spacedBy(10.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        repeat(3) {
            Box(
                modifier = Modifier
                    .size(11.dp)
                    .scale(dotScale)
                    .background(
                        color = AccentPink,
                        shape = CircleShape
                    )
            )
        }
    }
}

@Composable
private fun ActivatedScreen(
    wristbandId: String,
    onCloseApp: () -> Unit
) {
    LaunchedEffect(Unit) {
        delay(10_000)
        onCloseApp()
    }

    BoxWithConstraints(
        modifier = Modifier
            .fillMaxSize()
            .navigationBarsPadding()
    ) {
        val tight = maxHeight < 700.dp
        val compact = maxHeight < 760.dp
        val logoHeight = if (tight) {
            30.dp
        } else {
            38.dp
        }
        val animationSize = if (tight) {
            136.dp
        } else if (compact) {
            158.dp
        } else {
            180.dp
        }

        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(
                    horizontal = 28.dp,
                    vertical = if (tight) 24.dp else 36.dp
                ),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            CueLogoHeader(
                modifier = Modifier
                    .height(logoHeight)
                    .fillMaxWidth(0.30f)
            )

            Spacer(modifier = Modifier.weight(0.55f))

            ConfirmationAnimation(
                animationSize = animationSize
            )

            Spacer(modifier = Modifier.height(if (tight) 20.dp else 26.dp))

            SingleLineText(
                text = "Profile update successful",
                modifier = Modifier.fillMaxWidth(),
                color = InkBlack,
                maxFontSize = if (tight) 24.sp else 28.sp,
                fontWeight = FontWeight.Black,
                textAlign = TextAlign.Center,
                widthFactor = 0.60f
            )

            Spacer(modifier = Modifier.height(8.dp))

            Box(
                modifier = Modifier
                    .width(158.dp)
                    .height(4.dp)
                    .background(
                        color = AccentPink,
                        shape = RoundedCornerShape(50)
                    )
            )

            Spacer(modifier = Modifier.height(if (tight) 15.dp else 20.dp))

            SingleLineText(
                text = "${wristbandId.toWristbandDisplayName()} is ready.",
                modifier = Modifier.fillMaxWidth(),
                color = AccentPink,
                maxFontSize = if (tight) 16.sp else 18.sp,
                fontWeight = FontWeight.Black,
                textAlign = TextAlign.Center
            )

            Spacer(modifier = Modifier.height(if (tight) 11.dp else 15.dp))

            SingleLineText(
                text = "Put your phone in your pocket and enjoy the night.",
                modifier = Modifier.fillMaxWidth(),
                color = InkBlack,
                maxFontSize = if (tight) 16.sp else 18.sp,
                fontWeight = FontWeight.Medium,
                textAlign = TextAlign.Center,
                widthFactor = 0.50f
            )

            Spacer(modifier = Modifier.height(if (tight) 11.dp else 15.dp))

            SingleLineText(
                text = "This app will close automatically in 10 seconds.",
                modifier = Modifier.fillMaxWidth(),
                color = MutedGrey,
                maxFontSize = if (tight) 13.sp else 15.sp,
                fontWeight = FontWeight.Bold,
                textAlign = TextAlign.Center,
                widthFactor = 0.50f
            )

            Spacer(modifier = Modifier.weight(1f))
        }
    }
}

@Composable
private fun ConfirmationAnimation(
    animationSize: androidx.compose.ui.unit.Dp = 188.dp
) {
    val transition = rememberInfiniteTransition(
        label = "confirmationPulse"
    )

    val pulseScale by transition.animateFloat(
        initialValue = 0.94f,
        targetValue = 1.08f,
        animationSpec = infiniteRepeatable(
            animation = tween(
                durationMillis = 1100
            ),
            repeatMode = RepeatMode.Reverse
        ),
        label = "confirmationScale"
    )

    val ringAlpha by transition.animateFloat(
        initialValue = 0.30f,
        targetValue = 0.72f,
        animationSpec = infiniteRepeatable(
            animation = tween(
                durationMillis = 1100
            ),
            repeatMode = RepeatMode.Reverse
        ),
        label = "confirmationAlpha"
    )

    Canvas(
        modifier = Modifier
            .size(animationSize)
            .scale(pulseScale)
    ) {
        val center = Offset(
            x = size.width / 2f,
            y = size.height / 2f
        )
        val radius = size.minDimension * 0.30f

        drawCircle(
            color = SoftPink.copy(
                alpha = ringAlpha
            ),
            radius = size.minDimension * 0.44f,
            center = center
        )

        drawCircle(
            color = SoftPink,
            radius = size.minDimension * 0.35f,
            center = center
        )

        drawCircle(
            color = AccentPink,
            radius = radius,
            center = center
        )

        drawLine(
            color = Color.White,
            start = Offset(
                x = size.width * 0.36f,
                y = size.height * 0.52f
            ),
            end = Offset(
                x = size.width * 0.47f,
                y = size.height * 0.63f
            ),
            strokeWidth = 12f,
            cap = StrokeCap.Round
        )

        drawLine(
            color = Color.White,
            start = Offset(
                x = size.width * 0.47f,
                y = size.height * 0.63f
            ),
            end = Offset(
                x = size.width * 0.66f,
                y = size.height * 0.40f
            ),
            strokeWidth = 12f,
            cap = StrokeCap.Round
        )
    }
}

private enum class LookingFor(
    val label: String
) {
    MEN("MEN"),
    WOMEN("WOMEN"),
    EVERYONE("EVERYONE")
}

private enum class Gender(
    val label: String
) {
    MAN("MAN"),
    WOMAN("WOMAN"),
    NON_BINARY("NON-BINARY"),
    PREFER_NOT_TO_SAY("PREFER NOT TO SAY")
}

private enum class PersonalityType(
    val title: String,
    val description: String
) {
    SHY(
        title = "I'M SHY!",
        description = "Let the wristband blink when matched"
    ),

    BOLD_CONNECT(
        title = "BOLD CONNECT!",
        description = "You'll hear your name somehow"
    )
}

@Composable
private fun ProfileSetupScreen(
    wristbandId: String,
    isSaving: Boolean,
    saveStatus: String?,
    onScanAgain: () -> Unit,
    onSave: (
        name: String,
        age: String,
        gender: Gender,
        lookingFor: LookingFor
    ) -> Unit
) {
    var name by remember {
        mutableStateOf("")
    }

    var age by remember {
        mutableStateOf("")
    }

    var selectedGender by remember {
        mutableStateOf(Gender.PREFER_NOT_TO_SAY)
    }

    var selectedLookingFor by remember {
        mutableStateOf(LookingFor.EVERYONE)
    }

    BoxWithConstraints(
        modifier = Modifier
            .fillMaxSize()
    ) {
        val compact = maxHeight < 760.dp
        val tight = maxHeight < 700.dp
        val horizontalPadding = if (tight) {
            22.dp
        } else {
            26.dp
        }
        val verticalPadding = if (tight) {
            14.dp
        } else {
            22.dp
        }
        val logoHeight = if (tight) {
            28.dp
        } else {
            34.dp
        }
        val headingSize = if (tight) {
            24.sp
        } else {
            27.sp
        }
        val fieldHeight = if (tight) {
            50.dp
        } else {
            54.dp
        }
        val chipHeight = if (tight) {
            32.dp
        } else {
            36.dp
        }
        val sectionGap = if (compact) {
            10.dp
        } else {
            14.dp
        }

        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(
                    horizontal = horizontalPadding,
                    vertical = verticalPadding
                ),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            CueLogoHeader(
                modifier = Modifier
                    .height(logoHeight)
                    .fillMaxWidth(0.28f)
            )

            Spacer(modifier = Modifier.height(if (tight) 6.dp else 9.dp))

            SingleLineText(
                text = "PROFILE SETUP & PAIRING",
                modifier = Modifier.fillMaxWidth(),
                color = InkBlack,
                maxFontSize = headingSize,
                fontWeight = FontWeight.Black,
                textAlign = TextAlign.Center,
                widthFactor = 0.62f
            )

            Spacer(modifier = Modifier.height(5.dp))

            Box(
                modifier = Modifier
                    .width(150.dp)
                    .height(4.dp)
                    .background(
                        color = AccentPink,
                        shape = RoundedCornerShape(50)
                    )
            )

            Spacer(modifier = Modifier.height(sectionGap))

            SingleLineText(
                text = "1. WRISTBAND DETECTED",
                modifier = Modifier.fillMaxWidth(),
                color = InkBlack,
                maxFontSize = 15.sp,
                fontWeight = FontWeight.Bold,
                textAlign = TextAlign.Start
            )

            Spacer(modifier = Modifier.height(6.dp))

            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .background(
                        color = SoftPink,
                        shape = RoundedCornerShape(10.dp)
                    )
                    .border(
                        width = 2.dp,
                        color = AccentPink,
                        shape = RoundedCornerShape(10.dp)
                    )
                    .padding(
                        horizontal = 14.dp,
                        vertical = if (tight) 9.dp else 11.dp
                    )
            ) {
                SingleLineText(
                    text = "DETECTED: ${wristbandId.toWristbandDisplayName()}",
                    modifier = Modifier.fillMaxWidth(),
                    color = AccentPink,
                    maxFontSize = 16.sp,
                    fontWeight = FontWeight.Black,
                    textAlign = TextAlign.Start,
                    widthFactor = 0.58f
                )
            }

            Spacer(modifier = Modifier.height(4.dp))

            SingleLineText(
                text = "Scan a different wristband",
                modifier = Modifier
                    .align(Alignment.Start)
                    .fillMaxWidth()
                    .clickable(
                        onClick = onScanAgain
                    ),
                color = AccentPink,
                maxFontSize = 13.sp,
                fontWeight = FontWeight.Bold,
                textAlign = TextAlign.Start
            )

            Spacer(modifier = Modifier.height(sectionGap))

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                Column(
                    modifier = Modifier.weight(1.45f)
                ) {
                    FormLabel(
                        text = "NAME:"
                    )

                    OutlinedTextField(
                        value = name,
                        onValueChange = {
                            name = it
                        },
                        modifier = Modifier
                            .fillMaxWidth()
                            .height(fieldHeight),
                        placeholder = {
                            Text(
                                text = "[Jane Doe]",
                                color = MutedGrey,
                                fontSize = 13.sp
                            )
                        },
                        singleLine = true,
                        shape = RoundedCornerShape(10.dp)
                    )
                }

                Column(
                    modifier = Modifier.weight(0.65f)
                ) {
                    FormLabel(
                        text = "AGE:"
                    )

                    OutlinedTextField(
                        value = age,
                        onValueChange = { newValue ->
                            age = newValue
                                .filter { character ->
                                    character.isDigit()
                                }
                                .take(3)
                        },
                        modifier = Modifier
                            .fillMaxWidth()
                            .height(fieldHeight),
                        placeholder = {
                            Text(
                                text = "[25]",
                                color = MutedGrey,
                                fontSize = 13.sp
                            )
                        },
                        keyboardOptions = KeyboardOptions(
                            keyboardType = KeyboardType.Number
                        ),
                        singleLine = true,
                        shape = RoundedCornerShape(10.dp)
                    )
                }
            }

            Spacer(modifier = Modifier.height(sectionGap))

            FormLabel(
                text = "GENDER:"
            )

            CompactSelectionGrid(
                labels = Gender.entries.map { option ->
                    option.label
                },
                selectedIndex = Gender.entries.indexOf(selectedGender),
                chipHeight = chipHeight,
                onSelect = { selectedIndex ->
                    selectedGender = Gender.entries[selectedIndex]
                }
            )

            Spacer(modifier = Modifier.height(sectionGap))

            FormLabel(
                text = "LOOKING FOR:"
            )

            CompactSelectionGrid(
                labels = LookingFor.entries.map { option ->
                    option.label
                },
                selectedIndex = LookingFor.entries.indexOf(selectedLookingFor),
                chipHeight = chipHeight,
                onSelect = { selectedIndex ->
                    selectedLookingFor = LookingFor.entries[selectedIndex]
                }
            )

            Spacer(modifier = Modifier.weight(1f))

            Button(
                onClick = {
                    onSave(
                        name.trim(),
                        age.trim(),
                        selectedGender,
                        selectedLookingFor
                    )
                },
                modifier = Modifier
                    .fillMaxWidth()
                    .height(if (tight) 52.dp else 56.dp),
                enabled = name.isNotBlank() &&
                        age.isNotBlank() &&
                        !isSaving,
                colors = ButtonDefaults.buttonColors(
                    containerColor = AccentPink,
                    disabledContainerColor = SoftPink
                ),
                shape = RoundedCornerShape(14.dp),
                border = BorderStroke(
                    width = 2.dp,
                    color = InkBlack
                )
            ) {
                SingleLineText(
                    text = if (isSaving) {
                        "SAVING PROFILE..."
                    } else {
                        "SAVE PROFILE & START!"
                    },
                    modifier = Modifier.fillMaxWidth(),
                    color = Color.White,
                    maxFontSize = if (tight) 16.sp else 17.sp,
                    fontWeight = FontWeight.Black,
                    textAlign = TextAlign.Center,
                    widthFactor = 0.62f
                )
            }

            if (saveStatus != null) {
                Spacer(modifier = Modifier.height(6.dp))

                SingleLineText(
                    text = saveStatus,
                    modifier = Modifier.fillMaxWidth(),
                    color = AccentPink,
                    maxFontSize = 13.sp,
                    fontWeight = FontWeight.Bold,
                    textAlign = TextAlign.Center,
                    widthFactor = 0.48f
                )
            }
        }
    }
}

@Composable
private fun CompactSelectionGrid(
    labels: List<String>,
    selectedIndex: Int,
    chipHeight: androidx.compose.ui.unit.Dp,
    onSelect: (Int) -> Unit
) {
    labels.chunked(2).forEachIndexed { rowIndex, rowLabels ->
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            rowLabels.forEachIndexed { columnIndex, label ->
                val optionIndex = rowIndex * 2 + columnIndex
                SelectionChip(
                    label = label,
                    selected = selectedIndex == optionIndex,
                    modifier = Modifier
                        .weight(1f)
                        .height(chipHeight),
                    onClick = {
                        onSelect(optionIndex)
                    }
                )
            }

            if (rowLabels.size == 1) {
                Spacer(
                    modifier = Modifier.weight(1f)
                )
            }
        }

        if (rowIndex != labels.chunked(2).lastIndex) {
            Spacer(modifier = Modifier.height(7.dp))
        }
    }
}

@Composable
private fun SelectionChip(
    label: String,
    selected: Boolean,
    modifier: Modifier = Modifier,
    onClick: () -> Unit
) {
    Box(
        modifier = modifier
            .background(
                color = if (selected) {
                    SoftPink
                } else {
                    Color.White
                },
                shape = RoundedCornerShape(10.dp)
            )
            .border(
                width = if (selected) {
                    2.dp
                } else {
                    1.dp
                },
                color = if (selected) {
                    AccentPink
                } else {
                    InkBlack
                },
                shape = RoundedCornerShape(10.dp)
            )
            .clickable(
                onClick = onClick
            )
            .padding(
                horizontal = 8.dp
            ),
        contentAlignment = Alignment.Center
    ) {
        SingleLineText(
            text = label,
            modifier = Modifier.fillMaxWidth(),
            color = if (selected) {
                AccentPink
            } else {
                InkBlack
            },
            maxFontSize = 12.sp,
            minFontSize = 7.sp,
            fontWeight = FontWeight.Black,
            textAlign = TextAlign.Center,
            widthFactor = 0.58f
        )
    }
}

@Composable
private fun FormLabel(
    text: String
) {
    SingleLineText(
        text = text,
        modifier = Modifier.fillMaxWidth(),
        color = InkBlack,
        maxFontSize = 13.sp,
        fontWeight = FontWeight.Black,
        textAlign = TextAlign.Start
    )

    Spacer(modifier = Modifier.height(4.dp))
}

@Composable
private fun PersonalitySelectorScreen(
    onActivate: (
        selectedPersonality: PersonalityType
    ) -> Unit
) {
    var selectedPersonality by rememberSaveable {
        mutableStateOf<PersonalityType?>(null)
    }

    BoxWithConstraints(
        modifier = Modifier
            .fillMaxSize()
            .navigationBarsPadding()
    ) {
        val compact = maxHeight < 760.dp
        val tight = maxHeight < 700.dp
        val logoHeight = if (tight) {
            28.dp
        } else {
            34.dp
        }
        val headingSize = if (tight) {
            23.sp
        } else {
            25.sp
        }
        val imageHeight = if (tight) {
            118.dp
        } else if (compact) {
            136.dp
        } else {
            150.dp
        }
        val cardPadding = if (tight) {
            8.dp
        } else {
            10.dp
        }
        val cardTitleSize = if (tight) {
            16.sp
        } else {
            18.sp
        }
        val cardDescriptionSize = if (tight) {
            11.sp
        } else {
            12.sp
        }
        val verticalPadding = if (tight) {
            10.dp
        } else {
            14.dp
        }

        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(
                    horizontal = 22.dp,
                    vertical = verticalPadding
                ),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            CueLogoHeader(
                modifier = Modifier
                    .height(logoHeight)
                    .fillMaxWidth(0.24f)
            )

            Spacer(
                modifier = Modifier.height(if (tight) 7.dp else 10.dp)
            )

            SingleLineText(
                text = "INTERACTION PERSONALITY",
                modifier = Modifier.fillMaxWidth(),
                color = InkBlack,
                maxFontSize = headingSize,
                fontWeight = FontWeight.Black,
                textAlign = TextAlign.Center,
                widthFactor = 0.62f
            )

            Spacer(
                modifier = Modifier.height(5.dp)
            )

            Box(
                modifier = Modifier
                    .width(155.dp)
                    .height(4.dp)
                    .background(
                        color = AccentPink,
                        shape = RoundedCornerShape(50)
                    )
            )

            Spacer(
                modifier = Modifier.height(if (tight) 7.dp else 10.dp)
            )

            SingleLineText(
                text = "Choose how you'd like to connect",
                modifier = Modifier.fillMaxWidth(),
                color = InkBlack,
                maxFontSize = if (tight) 14.sp else 16.sp,
                fontWeight = FontWeight.Medium,
                textAlign = TextAlign.Center,
                widthFactor = 0.54f
            )

            Spacer(
                modifier = Modifier.height(if (tight) 8.dp else 11.dp)
            )

            PersonalityCard(
                personality = PersonalityType.SHY,
                imageResource = R.drawable.personality_shy,
                isSelected = selectedPersonality == PersonalityType.SHY,
                imageHeight = imageHeight,
                contentPadding = cardPadding,
                titleSize = cardTitleSize,
                descriptionSize = cardDescriptionSize,
                onClick = {
                    selectedPersonality = PersonalityType.SHY
                }
            )

            Spacer(
                modifier = Modifier.height(if (tight) 10.dp else 13.dp)
            )

            PersonalityCard(
                personality = PersonalityType.BOLD_CONNECT,
                imageResource = R.drawable.personality_bold,
                isSelected = selectedPersonality ==
                        PersonalityType.BOLD_CONNECT,
                imageHeight = imageHeight,
                contentPadding = cardPadding,
                titleSize = cardTitleSize,
                descriptionSize = cardDescriptionSize,
                onClick = {
                    selectedPersonality =
                        PersonalityType.BOLD_CONNECT
                }
            )

            Spacer(
                modifier = Modifier.height(if (tight) 8.dp else 10.dp)
            )

            Button(
                onClick = {
                    selectedPersonality?.let {
                        onActivate(it)
                    }
                },
                modifier = Modifier
                    .fillMaxWidth()
                    .height(if (tight) 52.dp else 56.dp),
                enabled = selectedPersonality != null,
                colors = ButtonDefaults.buttonColors(
                    containerColor = AccentPink,
                    contentColor = Color.White,
                    disabledContainerColor = Color(0xFFD2D2D2),
                    disabledContentColor = Color(0xFF777777)
                ),
                shape = RoundedCornerShape(15.dp),
                border = BorderStroke(
                    width = 2.dp,
                    color = if (selectedPersonality != null) {
                        InkBlack
                    } else {
                        Color(0xFFC5C5C5)
                    }
                )
            ) {
                SingleLineText(
                    text = "ACTIVATE VIBE & HIDE PHONE",
                    modifier = Modifier.fillMaxWidth(),
                    color = Color.White,
                    maxFontSize = if (tight) 15.sp else 16.sp,
                    minFontSize = 9.sp,
                    fontWeight = FontWeight.Black,
                    textAlign = TextAlign.Center,
                    widthFactor = 0.62f
                )
            }

            Spacer(
                modifier = Modifier.height(if (tight) 2.dp else 4.dp)
            )
        }
    }
}

@Composable
private fun PersonalityCard(
    personality: PersonalityType,
    imageResource: Int,
    isSelected: Boolean,
    imageHeight: androidx.compose.ui.unit.Dp,
    contentPadding: androidx.compose.ui.unit.Dp,
    titleSize: androidx.compose.ui.unit.TextUnit,
    descriptionSize: androidx.compose.ui.unit.TextUnit,
    onClick: () -> Unit
) {
    Surface(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(
                onClick = onClick
            ),
        shape = RoundedCornerShape(22.dp),
        color = if (isSelected) {
            SoftPink
        } else {
            Color.White
        },
        border = BorderStroke(
            width = if (isSelected) {
                3.dp
            } else {
                2.dp
            },
            color = if (isSelected) {
                AccentPink
            } else {
                InkBlack
            }
        ),
        shadowElevation = if (isSelected) {
            5.dp
        } else {
            2.dp
        }
    ) {
        Column(
            modifier = Modifier.padding(
                horizontal = contentPadding,
                vertical = contentPadding
            ),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            Box {
                Image(
                    painter = painterResource(
                        id = imageResource
                    ),
                    contentDescription = personality.title,
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(imageHeight),
                    contentScale = ContentScale.Crop
                )

                if (isSelected) {
                    Box(
                        modifier = Modifier
                            .align(
                                Alignment.TopEnd
                            )
                            .padding(8.dp)
                            .size(30.dp)
                            .background(
                                color = AccentPink,
                                shape = CircleShape
                            ),
                        contentAlignment = Alignment.Center
                    ) {
                        Text(
                            text = "✓",
                            color = Color.White,
                            fontSize = 20.sp,
                            fontWeight = FontWeight.Black
                        )
                    }
                }
            }

            Spacer(
                modifier = Modifier.height(6.dp)
            )

            SingleLineText(
                text = personality.title,
                modifier = Modifier.fillMaxWidth(),
                color = if (isSelected) {
                    AccentPink
                } else {
                    InkBlack
                },
                maxFontSize = titleSize,
                fontWeight = FontWeight.Black,
                textAlign = TextAlign.Center,
                widthFactor = 0.60f
            )

            Spacer(
                modifier = Modifier.height(2.dp)
            )

            SingleLineText(
                text = personality.description,
                modifier = Modifier.fillMaxWidth(),
                color = InkBlack,
                maxFontSize = descriptionSize,
                minFontSize = 8.sp,
                fontWeight = FontWeight.Medium,
                textAlign = TextAlign.Center,
                widthFactor = 0.48f
            )
        }
    }
}
