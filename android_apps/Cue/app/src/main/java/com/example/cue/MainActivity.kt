package com.example.cue

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.media.MediaRecorder
import android.net.Uri
import android.nfc.NfcAdapter
import android.nfc.NdefRecord
import android.nfc.Tag
import android.nfc.tech.Ndef
import android.os.Bundle
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.ComponentActivity
import androidx.activity.SystemBarStyle
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.snapshotFlow
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.platform.LocalContext
import androidx.core.content.ContextCompat
import com.example.cue.ui.theme.CueTheme
import com.example.cue.ui.theme.KoulenFontFamily
import com.google.firebase.firestore.FieldValue
import com.google.firebase.firestore.FirebaseFirestore
import com.google.firebase.storage.FirebaseStorage
import com.google.firebase.storage.StorageMetadata
import kotlinx.coroutines.delay
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.distinctUntilChanged
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLEncoder
import java.util.Base64
import java.util.LinkedHashMap
import java.io.File
import java.nio.charset.Charset

private val SplashPink = Color(0xFFF8C9E5)
private val CueBlack = Color(0xFF000000)
private val CueWhite = Color(0xFFFFFFFF)
private val CueMutedText = Color(0xFFB7B0B4)
private val CueSelectedChip = Color(0xFF7E536B)
private const val LargeLogoAspectRatio = 182f / 121f
private const val MediumLogoAspectRatio = 189f / 108f
private const val LastProfilePreferences = "cue_last_profile"

private data class LastProfile(
    val documentId: String,
    val name: String,
    val age: Int,
    val gender: String,
    val orientation: String,
    val hubPreference: String
)

private data class NfcScanResult(
    val nfcUid: String,
    val rfidEpc: String
)

private fun NfcScanResult.validationError(): String? {
    val missingFields = buildList {
        if (nfcUid.isBlank()) {
            add("NFC ID")
        }
        if (rfidEpc.isBlank()) {
            add("RFID value")
        }
    }

    if (missingFields.isEmpty()) {
        return null
    }

    return "Could not read ${missingFields.joinToString(" and ")}. Please scan your wristband again."
}

private fun Context.loadLastProfile(): LastProfile? {
    val preferences = getSharedPreferences(LastProfilePreferences, Context.MODE_PRIVATE)
    val documentId = preferences.getString("documentId", null).orEmpty()
    if (documentId.isBlank()) {
        return null
    }

    return LastProfile(
        documentId = documentId,
        name = preferences.getString("name", "").orEmpty(),
        age = preferences.getInt("age", 0),
        gender = preferences.getString("gender", "").orEmpty(),
        orientation = preferences.getString("orientation", "").orEmpty(),
        hubPreference = preferences.getString("hubPreference", "").orEmpty()
    )
}

private fun Context.saveLastProfile(
    documentId: String,
    form: OnboardingFormState
) {
    getSharedPreferences(LastProfilePreferences, Context.MODE_PRIVATE)
        .edit()
        .putString("documentId", documentId)
        .putString("name", form.name.trim())
        .putInt("age", form.age)
        .putString("gender", form.identity.orEmpty())
        .putString("orientation", form.orientation)
        .putString(
            "hubPreference",
            form.selectedTrack?.let {
                "${it.title} / ${it.artists}"
            } ?: form.cueChoice.orEmpty()
        )
        .apply()
}

private fun uploadWristbandScan(
    profile: LastProfile,
    scan: NfcScanResult,
    onSuccess: () -> Unit,
    onFailure: (String) -> Unit
) {
    scan.validationError()?.let { error ->
        onFailure(error)
        return
    }

    FirebaseFirestore
        .getInstance()
        .collection("profiles")
        .document(profile.documentId)
        .update(
            mapOf(
                "nfcUid" to scan.nfcUid,
                "rfidEpc" to scan.rfidEpc,
                "wristband" to mapOf(
                    "nfcUid" to scan.nfcUid,
                    "rfidEpc" to scan.rfidEpc
                ),
                "status" to "WRISTBAND_SCANNED",
                "updatedAt" to FieldValue.serverTimestamp()
            )
        )
        .addOnSuccessListener {
            onSuccess()
        }
        .addOnFailureListener { error ->
            onFailure(error.message ?: "Could not upload wristband scan.")
        }
}

private class OnboardingFormState {
    var name by mutableStateOf("")
    var pronunciationFileName by mutableStateOf<String?>(null)
    var pronunciationFilePath by mutableStateOf<String?>(null)
    var identity by mutableStateOf<String?>(null)
    var identityOther by mutableStateOf("")
    var orientation by mutableStateOf("Heterosexual")
    var orientationOther by mutableStateOf("")
    var age by mutableIntStateOf(25)
    var matchMinAge by mutableIntStateOf(20)
    var matchMaxAge by mutableIntStateOf(25)
    var cueChoice by mutableStateOf<String?>(null)
    var matchedPreference by mutableStateOf<String?>(null)
    var selectedTrack by mutableStateOf<SoundCloudTrack?>(null)
    var instagram by mutableStateOf("")
    var snapchat by mutableStateOf("")
    var whatsapp by mutableStateOf("")
}

private fun validateFirstQuestionPage(
    form: OnboardingFormState
): String? {
    return when {
        form.name.isBlank() -> {
            "Please fill in your name."
        }

        form.identity == null -> {
            "Please choose how you identify."
        }

        form.identity == "Other" && form.identityOther.isBlank() -> {
            "Please type your identity."
        }

        form.orientation.isBlank() -> {
            "Please choose or type your sexual orientation."
        }

        else -> {
            null
        }
    }
}

private fun validateHubCuePage(
    form: OnboardingFormState
): String? {
    val songRequired = form.cueChoice == "song" || form.cueChoice == "either!"

    return when {
        form.cueChoice == null -> {
            "Please choose how the hub should cue you."
        }

        form.matchedPreference == null -> {
            "Please choose what you want after being matched."
        }

        songRequired && form.selectedTrack == null -> {
            "Please choose a SoundCloud song."
        }

        else -> {
            null
        }
    }
}

private fun OnboardingFormState.toFirestorePayload(
    pronunciationDownloadUrl: String?,
    pronunciationStoragePath: String?
): Map<String, Any?> {
    val track = selectedTrack
    return mapOf(
        "source" to "cue_onboarding",
        "status" to "ONBOARDING_SUBMITTED",
        "name" to name.trim(),
        "nickname" to name.trim(),
        "pronunciation" to mapOf(
            "fileName" to pronunciationFileName,
            "localPath" to pronunciationFilePath,
            "storagePath" to pronunciationStoragePath,
            "downloadUrl" to pronunciationDownloadUrl
        ),
        "identity" to identity,
        "gender" to identity,
        "identityOther" to identityOther.trim(),
        "orientation" to orientation,
        "lookingFor" to orientation,
        "orientationOther" to orientationOther.trim(),
        "age" to age,
        "matchAgeRange" to mapOf(
            "min" to matchMinAge,
            "max" to matchMaxAge
        ),
        "cueChoice" to cueChoice,
        "matchedPreference" to matchedPreference,
        "soundCloudTrack" to track?.let {
            mapOf(
                "id" to it.id,
                "title" to it.title,
                "artists" to it.artists,
                "album" to it.album,
                "url" to it.url
            )
        },
        "socials" to mapOf(
            "instagram" to instagram.trim(),
            "snapchat" to snapchat.trim(),
            "whatsapp" to whatsapp.trim()
        ),
        "createdAt" to FieldValue.serverTimestamp(),
        "updatedAt" to FieldValue.serverTimestamp()
    )
}

private fun uploadOnboardingForm(
    form: OnboardingFormState,
    onSuccess: (String) -> Unit,
    onFailure: (String) -> Unit
) {
    val firestore = FirebaseFirestore.getInstance()

    fun saveProfile(
        pronunciationDownloadUrl: String?,
        pronunciationStoragePath: String?
    ) {
        firestore
            .collection("profiles")
            .add(
                form.toFirestorePayload(
                    pronunciationDownloadUrl = pronunciationDownloadUrl,
                    pronunciationStoragePath = pronunciationStoragePath
                )
            )
            .addOnSuccessListener { documentReference ->
                onSuccess(documentReference.id)
            }
            .addOnFailureListener { error ->
                onFailure("Firestore profile upload failed: ${error.message ?: "Could not upload your answers."}")
            }
    }

    val pronunciationPath = form.pronunciationFilePath
    if (pronunciationPath == null) {
        saveProfile(
            pronunciationDownloadUrl = null,
            pronunciationStoragePath = null
        )
        return
    }

    val pronunciationFile = File(pronunciationPath)
    if (!pronunciationFile.exists()) {
        saveProfile(
            pronunciationDownloadUrl = null,
            pronunciationStoragePath = null
        )
        return
    }

    val storagePath = "pronunciations/${System.currentTimeMillis()}_${pronunciationFile.name}"
    val storageRef = FirebaseStorage
        .getInstance()
        .reference
        .child(storagePath)

    storageRef
        .putFile(
            Uri.fromFile(pronunciationFile),
            StorageMetadata.Builder()
                .setContentType("audio/mp4")
                .build()
        )
        .addOnSuccessListener {
            saveProfile(
                pronunciationDownloadUrl = null,
                pronunciationStoragePath = storagePath
            )
        }
        .addOnFailureListener { error ->
            saveProfile(
                pronunciationDownloadUrl = null,
                pronunciationStoragePath = null
            )
        }
}

private class PronunciationRecorder(
    private val context: Context
) {
    private var recorder: MediaRecorder? = null
    private var outputFile: File? = null

    fun start(): File {
        release()

        val directory = File(context.filesDir, "pronunciations").apply {
            mkdirs()
        }
        val file = File(
            directory,
            "pronunciation_${System.currentTimeMillis()}.m4a"
        )

        recorder = MediaRecorder(context).apply {
            setAudioSource(MediaRecorder.AudioSource.MIC)
            setOutputFormat(MediaRecorder.OutputFormat.MPEG_4)
            setAudioEncoder(MediaRecorder.AudioEncoder.AAC)
            setAudioEncodingBitRate(128_000)
            setAudioSamplingRate(44_100)
            setOutputFile(file.absolutePath)
            prepare()
            start()
        }
        outputFile = file
        return file
    }

    fun stop(): File? {
        val file = outputFile
        runCatching {
            recorder?.stop()
        }.onFailure {
            file?.delete()
            outputFile = null
        }
        release()
        return file?.takeIf {
            it.exists()
        }
    }

    fun release() {
        recorder?.let { activeRecorder ->
            runCatching {
                activeRecorder.reset()
                activeRecorder.release()
            }
        }
        recorder = null
    }
}

private data class SoundCloudTrack(
    val id: String,
    val title: String,
    val artists: String,
    val album: String,
    val url: String
)

private object SoundCloudApiClient {
    private var accessToken: String? = null
    private var refreshToken: String? = null
    private var tokenExpiresAtMillis: Long = 0L

    suspend fun searchTracks(query: String): Result<List<SoundCloudTrack>> {
        return withContext(Dispatchers.IO) {
            runCatching {
                val trimmedQuery = query.trim()
                if (looksLikeSoundCloudUrl(trimmedQuery)) {
                    return@runCatching listOf(resolveTrackUrl(trimmedQuery))
                }

                val token = getAccessToken()
                val tracksByKey = LinkedHashMap<String, SoundCloudTrack>()

                searchQueryVariants(trimmedQuery).forEach { searchQuery ->
                    val encodedQuery = URLEncoder.encode(searchQuery, "UTF-8")
                    val url = URL(
                        "https://api.soundcloud.com/tracks" +
                            "?q=$encodedQuery&access=playable&limit=25&linked_partitioning=true"
                    )
                    val connection = (url.openConnection() as HttpURLConnection).apply {
                        requestMethod = "GET"
                        setRequestProperty("Authorization", "OAuth $token")
                        setRequestProperty("Accept", "application/json; charset=utf-8")
                        connectTimeout = 10_000
                        readTimeout = 10_000
                    }

                    val body = connection.readResponseBody()
                    if (connection.responseCode !in 200..299) {
                        throw IllegalStateException("SoundCloud search failed: ${connection.responseCode} $body")
                    }

                    parseSearchResponse(body).forEach { track ->
                        val key = track.id.ifBlank {
                            track.url
                        }
                        tracksByKey.putIfAbsent(key, track)
                    }
                }

                tracksByKey.values.toList()
            }
        }
    }

    private fun parseSearchResponse(body: String): List<SoundCloudTrack> {
        val json = JSONObject(body)
        val collection = json.optJSONArray("collection")
            ?: throw IllegalStateException("SoundCloud response did not include tracks.")

        return List(collection.length()) { index ->
            val item = collection.getJSONObject(index)
            val user = item.optJSONObject("user")
            val artistName = user?.optString("username").orEmpty()
            val permalinkUrl = item.optString("permalink_url")

            SoundCloudTrack(
                id = item.getLong("id").toString(),
                title = item.optString("title", "Untitled track"),
                artists = artistName.ifBlank {
                    "SoundCloud artist"
                },
                album = item.optString("genre").ifBlank {
                    "SoundCloud"
                },
                url = permalinkUrl.ifBlank {
                    "https://soundcloud.com"
                }
            )
        }
    }

    private fun resolveTrackUrl(trackUrl: String): SoundCloudTrack {
        val normalisedUrl = normaliseSoundCloudUrl(trackUrl)
        val token = getAccessToken()
        runCatching {
            resolveTrackUrlWithApi(normalisedUrl, token)
        }.getOrNull()?.let {
            return it
        }

        return resolveTrackUrlWithOembed(normalisedUrl)
    }

    private fun resolveTrackUrlWithApi(trackUrl: String, token: String): SoundCloudTrack {
        val encodedUrl = URLEncoder.encode(trackUrl, "UTF-8")
        val url = URL("https://api.soundcloud.com/resolve?url=$encodedUrl")
        val connection = (url.openConnection() as HttpURLConnection).apply {
            requestMethod = "GET"
            setRequestProperty("Authorization", "OAuth $token")
            setRequestProperty("Accept", "application/json; charset=utf-8")
            connectTimeout = 10_000
            readTimeout = 10_000
        }

        val body = connection.readResponseBody()
        if (connection.responseCode !in 200..299) {
            throw IllegalStateException("SoundCloud URL resolve failed: ${connection.responseCode} $body")
        }

        val item = JSONObject(body)
        val user = item.optJSONObject("user")
        val artistName = user?.optString("username").orEmpty()
        val permalinkUrl = item.optString("permalink_url").ifBlank {
            trackUrl
        }

        return SoundCloudTrack(
            id = item.getLong("id").toString(),
            title = item.optString("title", "Untitled track"),
            artists = artistName.ifBlank {
                "SoundCloud artist"
            },
            album = item.optString("genre").ifBlank {
                "SoundCloud"
            },
            url = permalinkUrl
        )
    }

    private fun resolveTrackUrlWithOembed(trackUrl: String): SoundCloudTrack {
        val normalisedUrl = normaliseSoundCloudUrl(trackUrl)
        val encodedUrl = URLEncoder.encode(normalisedUrl, "UTF-8")
        val url = URL("https://soundcloud.com/oembed?format=json&url=$encodedUrl")
        val connection = (url.openConnection() as HttpURLConnection).apply {
            requestMethod = "GET"
            setRequestProperty("Accept", "application/json; charset=utf-8")
            connectTimeout = 10_000
            readTimeout = 10_000
        }

        val body = connection.readResponseBody()
        if (connection.responseCode !in 200..299) {
            throw IllegalStateException("SoundCloud URL lookup failed: ${connection.responseCode} $body")
        }

        val json = JSONObject(body)
        val title = json.optString("title", "SoundCloud track")
        val artist = json.optString("author_name", "SoundCloud artist")

        return SoundCloudTrack(
            id = "url:$normalisedUrl",
            title = title,
            artists = artist,
            album = "SoundCloud",
            url = normalisedUrl
        )
    }

    private fun searchQueryVariants(query: String): List<String> {
        val compactPunctuation = query
            .replace(".", "")
            .replace("\$", "")
            .replace(Regex("\\s+"), " ")
            .trim()
        val spacedPunctuation = query
            .replace(".", " ")
            .replace("\$", " ")
            .replace(Regex("\\s+"), " ")
            .trim()

        return listOf(query, compactPunctuation, spacedPunctuation)
            .map {
                it.trim()
            }
            .filter {
                it.length >= 2
            }
            .distinct()
    }

    private fun looksLikeSoundCloudUrl(value: String): Boolean {
        val host = runCatching {
            Uri.parse(value).host.orEmpty().lowercase()
        }.getOrDefault("")

        return host == "soundcloud.com" || host == "www.soundcloud.com"
    }

    private fun normaliseSoundCloudUrl(value: String): String {
        val uri = Uri.parse(value.trim())
        val scheme = uri.scheme ?: "https"
        val host = uri.host ?: "soundcloud.com"
        val path = uri.path.orEmpty().trimEnd('/')

        return "$scheme://$host$path"
    }

    private fun getAccessToken(): String {
        val now = System.currentTimeMillis()
        accessToken?.takeIf {
            now < tokenExpiresAtMillis
        }?.let {
            return it
        }

        val clientId = BuildConfig.SOUNDCLOUD_CLIENT_ID
        val clientSecret = BuildConfig.SOUNDCLOUD_CLIENT_SECRET
        if (clientId.isBlank() || clientSecret.isBlank()) {
            throw IllegalStateException(
                "Missing soundcloud.client.id or soundcloud.client.secret in local.properties."
            )
        }

        val auth = Base64.getEncoder()
            .encodeToString("$clientId:$clientSecret".toByteArray(Charsets.UTF_8))
        val connection = (URL("https://secure.soundcloud.com/oauth/token")
            .openConnection() as HttpURLConnection).apply {
            requestMethod = "POST"
            doOutput = true
            setRequestProperty("Authorization", "Basic $auth")
            setRequestProperty("Content-Type", "application/x-www-form-urlencoded")
            setRequestProperty("Accept", "application/json; charset=utf-8")
            connectTimeout = 10_000
            readTimeout = 10_000
        }

        connection.outputStream.use { output ->
            output.write("grant_type=client_credentials".toByteArray(Charsets.UTF_8))
        }

        val body = connection.readResponseBody()
        if (connection.responseCode !in 200..299) {
            throw IllegalStateException("SoundCloud token failed: ${connection.responseCode} $body")
        }

        val json = JSONObject(body)
        val token = json.getString("access_token")
        val expiresInSeconds = json.getLong("expires_in")
        accessToken = token
        refreshToken = json.optString("refresh_token").takeIf {
            it.isNotBlank()
        }
        tokenExpiresAtMillis = now + (expiresInSeconds - 60L) * 1000L
        return token
    }

    private fun HttpURLConnection.readResponseBody(): String {
        val stream = if (responseCode in 200..299) {
            inputStream
        } else {
            errorStream ?: inputStream
        }

        return stream.bufferedReader().use { reader ->
            reader.readText()
        }
    }
}

class MainActivity : ComponentActivity(), NfcAdapter.ReaderCallback {
    private var nfcAdapter: NfcAdapter? = null
    private var nfcScanHandler: ((NfcScanResult) -> Unit)? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        nfcAdapter = NfcAdapter.getDefaultAdapter(this)

        enableEdgeToEdge(
            statusBarStyle = SystemBarStyle.light(
                scrim = SplashPink.toArgb(),
                darkScrim = CueBlack.toArgb()
            ),
            navigationBarStyle = SystemBarStyle.light(
                scrim = SplashPink.toArgb(),
                darkScrim = CueBlack.toArgb()
            )
        )

        setContent {
            CueTheme {
                CueOnboarding(
                    onSetNfcScanHandler = { handler ->
                        setNfcScanHandler(handler)
                    },
                    onExitApp = {
                        finishAndRemoveTask()
                    }
                )
            }
        }
    }

    override fun onPause() {
        super.onPause()
        nfcAdapter?.disableReaderMode(this)
    }

    override fun onTagDiscovered(tag: Tag) {
        val scan = NfcScanResult(
            nfcUid = tag.id.toHexString().trim(),
            rfidEpc = tag.readNdefValue().orEmpty().trim()
        )

        runOnUiThread {
            nfcScanHandler?.invoke(scan)
        }
    }

    private fun setNfcScanHandler(
        handler: ((NfcScanResult) -> Unit)?
    ) {
        nfcScanHandler = handler

        if (handler == null) {
            nfcAdapter?.disableReaderMode(this)
            return
        }

        val adapter = nfcAdapter ?: return
        if (!adapter.isEnabled) {
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
}

private fun ByteArray.toHexString(): String {
    return joinToString(separator = "") { byte ->
        "%02X".format(byte)
    }
}

private fun Tag.readNdefValue(): String? {
    val ndef = Ndef.get(this) ?: return null
    return runCatching {
        ndef.connect()
        val message = ndef.ndefMessage ?: ndef.cachedNdefMessage
        message
            ?.records
            ?.firstOrNull()
            ?.toTextPayload()
    }.getOrNull().also {
        runCatching {
            ndef.close()
        }
    }
}

private fun NdefRecord.toTextPayload(): String {
    val payload = payload
    if (payload.isEmpty()) {
        return ""
    }

    if (tnf == NdefRecord.TNF_WELL_KNOWN && type.contentEquals(NdefRecord.RTD_TEXT)) {
        val languageCodeLength = payload[0].toInt() and 0x3F
        val encoding = if ((payload[0].toInt() and 0x80) == 0) {
            Charsets.UTF_8
        } else {
            Charset.forName("UTF-16")
        }
        return payload
            .copyOfRange(1 + languageCodeLength, payload.size)
            .toString(encoding)
    }

    return payload.toString(Charsets.UTF_8)
}

@Composable
private fun CueOnboarding(
    onSetNfcScanHandler: (((NfcScanResult) -> Unit)?) -> Unit,
    onExitApp: () -> Unit
) {
    val context = LocalContext.current
    var screen by remember {
        mutableIntStateOf(0)
    }
    val splashAlpha = remember {
        Animatable(1f)
    }
    val secondCardAlpha = remember {
        Animatable(0f)
    }
    val personaliseSlideProgress = remember {
        Animatable(1f)
    }
    var introCanAdvance by remember {
        mutableStateOf(false)
    }
    var transitionInProgress by remember {
        mutableStateOf(false)
    }
    val form = remember {
        OnboardingFormState()
    }
    var firstPageError by remember {
        mutableStateOf<String?>(null)
    }
    var hubPageMessage by remember {
        mutableStateOf<String?>(null)
    }
    var uploadInProgress by remember {
        mutableStateOf(false)
    }
    var lastProfile by remember {
        mutableStateOf<LastProfile?>(null)
    }
    var nfcMessage by remember {
        mutableStateOf<String?>(null)
    }
    var nfcUploadInProgress by remember {
        mutableStateOf(false)
    }
    val coroutineScope = rememberCoroutineScope()

    fun advanceToPersonalise() {
        if (!introCanAdvance || transitionInProgress || (screen != 1 && screen != 5)) {
            return
        }

        transitionInProgress = true
        coroutineScope.launch {
            personaliseSlideProgress.snapTo(1f)
            screen = 2
            personaliseSlideProgress.animateTo(
                targetValue = 0f,
                animationSpec = tween(durationMillis = 720)
            )
            transitionInProgress = false
        }
    }

    fun advanceAfterIntro() {
        lastProfile = context.loadLastProfile()
        if (lastProfile == null) {
            advanceToPersonalise()
        } else {
            screen = 5
        }
    }

    LaunchedEffect(Unit) {
        delay(900)
        splashAlpha.animateTo(
            targetValue = 0f,
            animationSpec = tween(durationMillis = 900)
        )
        screen = 1
        delay(700)
        secondCardAlpha.animateTo(
            targetValue = 1f,
            animationSpec = tween(durationMillis = 850)
        )
        introCanAdvance = true
    }

    BoxWithConstraints(
        modifier = Modifier
            .fillMaxSize()
            .background(CueBlack)
    ) {
        val slideOffset = maxHeight * personaliseSlideProgress.value

        when (screen) {
            1 -> {
                IntroExplainerScreen(
                    secondCardAlpha = secondCardAlpha.value,
                    onAdvance = ::advanceAfterIntro
                )
            }

            2 -> {
                PersonaliseExperienceScreen(
                    modifier = Modifier.offset(y = slideOffset),
                    onExit = onExitApp,
                    onNext = {
                        screen = 3
                    }
                )
            }

            3 -> {
                NextPlaceholderScreen(
                    form = form,
                    errorMessage = firstPageError,
                    onExit = onExitApp,
                    onNext = {
                        val validationError = validateFirstQuestionPage(form)
                        if (validationError == null) {
                            firstPageError = null
                            screen = 4
                        } else {
                            firstPageError = validationError
                        }
                    }
                )
            }

            4 -> {
                HubCueQuestionScreen(
                    form = form,
                    message = hubPageMessage,
                    uploadInProgress = uploadInProgress,
                    onExit = onExitApp,
                    onBack = {
                        if (uploadInProgress) {
                            return@HubCueQuestionScreen
                        }

                        val validationError = validateHubCuePage(form)
                        if (validationError != null) {
                            hubPageMessage = validationError
                            return@HubCueQuestionScreen
                        }

                        uploadInProgress = true
                        hubPageMessage = "Uploading your answers..."
                        uploadOnboardingForm(
                            form = form,
                            onSuccess = { documentId ->
                                context.saveLastProfile(
                                    documentId = documentId,
                                    form = form
                                )
                                lastProfile = context.loadLastProfile()
                                uploadInProgress = false
                                hubPageMessage = null
                                screen = 9
                            },
                            onFailure = { error ->
                                uploadInProgress = false
                                hubPageMessage = error
                            }
                        )
                    }
                )
            }

            5 -> {
                lastProfile?.let { profile ->
                    SavedProfileScreen(
                        profile = profile,
                        onScanWristband = {
                            screen = 6
                        },
                        onChangeProfile = {
                            advanceToPersonalise()
                        }
                    )
                }
            }

            6 -> {
                WristbandIntroScreen(
                    onExit = onExitApp,
                    onProceedToScan = {
                        nfcMessage = null
                        screen = 7
                    }
                )
            }

            7 -> {
                val profile = lastProfile
                if (profile != null) {
                    WristbandScanningScreen(
                        message = nfcMessage,
                        onExit = onExitApp,
                        onBack = {
                            onSetNfcScanHandler(null)
                            screen = 6
                        }
                    )

                    DisposableEffect(profile) {
                        onSetNfcScanHandler { scan ->
                            if (nfcUploadInProgress) {
                                return@onSetNfcScanHandler
                            }

                            scan.validationError()?.let { error ->
                                nfcMessage = error
                                return@onSetNfcScanHandler
                            }

                            nfcUploadInProgress = true
                            nfcMessage = "Uploading wristband..."
                            uploadWristbandScan(
                                profile = profile,
                                scan = scan,
                                onSuccess = {
                                    nfcUploadInProgress = false
                                    onSetNfcScanHandler(null)
                                    screen = 8
                                },
                                onFailure = { error ->
                                    nfcUploadInProgress = false
                                    nfcMessage = error
                                }
                            )
                        }

                        onDispose {
                            onSetNfcScanHandler(null)
                        }
                    }
                }
            }

            8 -> {
                WristbandCompleteScreen(
                    onExit = onExitApp,
                    onDone = onExitApp
                )
            }

            9 -> {
                ProfileCompletedScreen(
                    onExit = onExitApp,
                    onProceedToEvent = {
                        screen = 6
                    },
                    onBackToThursday = onExitApp
                )
            }
        }

        if (screen == 0 && splashAlpha.value > 0f) {
            SplashScreen(
                modifier = Modifier.alpha(splashAlpha.value)
            )
        }

    }
}

@Composable
private fun SplashScreen(
    modifier: Modifier = Modifier
) {
    Box(
        modifier = modifier
            .fillMaxSize()
            .background(SplashPink)
            .statusBarsPadding()
            .navigationBarsPadding(),
        contentAlignment = Alignment.Center
    ) {
        Image(
            painter = painterResource(id = R.drawable.cue_logo_large),
            contentDescription = "Cue",
            modifier = Modifier
                .fillMaxWidth(0.85f)
                .aspectRatio(LargeLogoAspectRatio),
            contentScale = ContentScale.Fit
        )
    }
}

@Composable
private fun SavedProfileScreen(
    profile: LastProfile,
    onScanWristband: () -> Unit,
    onChangeProfile: () -> Unit
) {
    BoxWithConstraints(
        modifier = Modifier
            .fillMaxSize()
            .background(CueBlack)
            .statusBarsPadding()
            .navigationBarsPadding()
    ) {
        val screenWidth = maxWidth
        val screenHeight = maxHeight
        val horizontalInset = screenWidth * 0.08f
        val logoTop = screenHeight * 0.035f

        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(horizontal = horizontalInset)
                .padding(top = logoTop)
        ) {
            WhiteCueLogo(
                modifier = Modifier.width(screenWidth * 0.24f)
            )

            Spacer(modifier = Modifier.height(screenHeight * 0.035f))

            Text(
                text = "PROFILE:",
                color = SplashPink,
                fontSize = 26.sp,
                lineHeight = 30.sp,
                fontFamily = KoulenFontFamily,
                letterSpacing = 0.sp
            )

            Spacer(modifier = Modifier.height(14.dp))

            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .border(
                        width = 1.dp,
                        color = CueWhite,
                        shape = RoundedCornerShape(22.dp)
                    )
                    .padding(horizontal = 16.dp, vertical = 14.dp)
            ) {
                Text(
                    text = "Name: ${profile.name}\n" +
                        "Age: ${profile.age}\n" +
                        "Gender: ${profile.gender}\n" +
                        "Sexual Orientation: ${profile.orientation}\n" +
                        "Hub Preference: ${profile.hubPreference}",
                    color = CueMutedText,
                    fontSize = 20.sp,
                    lineHeight = 23.sp,
                    fontWeight = FontWeight.Bold,
                    letterSpacing = 0.sp
                )
            }
        }

        ProfileActionButton(
            text = "I'm at the event!\n(Scan the wristband)",
            modifier = Modifier
                .fillMaxWidth(0.48f)
                .align(Alignment.BottomCenter)
                .offset(y = -screenHeight * 0.20f),
            onClick = onScanWristband
        )

        ProfileActionButton(
            text = "I want to change\nmy profile",
            modifier = Modifier
                .fillMaxWidth(0.48f)
                .align(Alignment.BottomCenter)
                .offset(y = -screenHeight * 0.10f),
            onClick = onChangeProfile
        )
    }
}

@Composable
private fun ProfileCompletedScreen(
    onExit: () -> Unit,
    onProceedToEvent: () -> Unit,
    onBackToThursday: () -> Unit
) {
    BoxWithConstraints(
        modifier = Modifier
            .fillMaxSize()
            .background(CueBlack)
            .statusBarsPadding()
            .navigationBarsPadding()
    ) {
        val screenWidth = maxWidth
        val screenHeight = maxHeight
        val horizontalInset = screenWidth * 0.055f
        val logoTop = screenHeight * 0.035f
        val closeSize = screenWidth * 0.09f

        HeaderLogoAndClose(
            screenWidth = screenWidth,
            logoWidth = screenWidth * 0.27f,
            horizontalInset = horizontalInset,
            top = logoTop,
            closeSize = closeSize,
            onExit = onExit
        )

        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(top = screenHeight * 0.17f, bottom = screenHeight * 0.08f),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            ProfileCompletedMark(
                modifier = Modifier
                    .fillMaxWidth(0.60f)
                    .height(screenHeight * 0.23f)
            )

            Spacer(modifier = Modifier.height(screenHeight * 0.05f))

            CueMouthPanel(
                modifier = Modifier
                    .fillMaxWidth()
                    .height(screenHeight * 0.15f),
                onClick = onProceedToEvent
            )

            Spacer(modifier = Modifier.height(14.dp))

            PinkActionButton(
                text = "PROCEED TO EVENT",
                modifier = Modifier.fillMaxWidth(0.52f),
                onClick = onProceedToEvent
            )

            Spacer(modifier = Modifier.height(12.dp))

            PinkActionButton(
                text = "BACK TO THURSDAY",
                modifier = Modifier.fillMaxWidth(0.52f),
                onClick = onBackToThursday
            )
        }
    }
}

@Composable
private fun ProfileCompletedMark(
    modifier: Modifier = Modifier
) {
    Image(
        painter = painterResource(id = R.drawable.profile_completed_graphic),
        contentDescription = "Profile completed",
        modifier = modifier,
        contentScale = ContentScale.Fit
    )
}

@Composable
private fun ProfileActionButton(
    text: String,
    modifier: Modifier,
    onClick: () -> Unit
) {
    Box(
        modifier = modifier
            .border(
                width = 1.dp,
                color = CueWhite,
                shape = RoundedCornerShape(20.dp)
            )
            .clickable(onClick = onClick)
            .padding(vertical = 12.dp, horizontal = 12.dp),
        contentAlignment = Alignment.Center
    ) {
        Text(
            text = text,
            color = CueMutedText,
            fontSize = 18.sp,
            lineHeight = 22.sp,
            textAlign = TextAlign.Center,
            letterSpacing = 0.sp
        )
    }
}

@Composable
private fun HeaderLogoAndClose(
    screenWidth: androidx.compose.ui.unit.Dp,
    logoWidth: androidx.compose.ui.unit.Dp,
    horizontalInset: androidx.compose.ui.unit.Dp,
    top: androidx.compose.ui.unit.Dp,
    closeSize: androidx.compose.ui.unit.Dp,
    onExit: () -> Unit
) {
    WhiteCueLogo(
        modifier = Modifier
            .offset(x = horizontalInset, y = top)
            .width(logoWidth)
    )

    CloseButton(
        modifier = Modifier
            .offset(
                x = screenWidth - horizontalInset - closeSize,
                y = top
            )
            .size(closeSize),
        onClick = onExit
    )
}

@Composable
private fun WristbandIntroScreen(
    onExit: () -> Unit,
    onProceedToScan: () -> Unit
) {
    BoxWithConstraints(
        modifier = Modifier
            .fillMaxSize()
            .background(CueBlack)
            .statusBarsPadding()
            .navigationBarsPadding()
            .clickable(onClick = onProceedToScan)
    ) {
        val screenWidth = maxWidth
        val screenHeight = maxHeight
        val horizontalInset = screenWidth * 0.06f
        val contentInset = screenWidth * 0.085f
        val logoTop = screenHeight * 0.035f
        val closeSize = screenWidth * 0.09f

        HeaderLogoAndClose(
            screenWidth = screenWidth,
            logoWidth = screenWidth * 0.27f,
            horizontalInset = horizontalInset,
            top = logoTop,
            closeSize = closeSize,
            onExit = onExit
        )

        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(horizontal = contentInset)
                .padding(top = screenHeight * 0.17f, bottom = screenHeight * 0.08f),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            Text(
                text = "SCAN YOUR WRISTBAND:",
                color = SplashPink,
                fontSize = 26.sp,
                lineHeight = 30.sp,
                fontFamily = KoulenFontFamily,
                textAlign = TextAlign.Center,
                letterSpacing = 0.sp
            )

            Spacer(modifier = Modifier.height(16.dp))

            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .border(
                        width = 1.dp,
                        color = CueWhite,
                        shape = RoundedCornerShape(18.dp)
                    )
                    .padding(horizontal = 18.dp, vertical = 12.dp),
                contentAlignment = Alignment.Center
            ) {
                Text(
                    text = "to scan your wristband, tap this\npart of your wristband at the back\nof your phone.",
                    color = CueMutedText,
                    fontSize = 16.sp,
                    lineHeight = 18.sp,
                    textAlign = TextAlign.Center
                )
            }

            Spacer(modifier = Modifier.height(screenHeight * 0.045f))

            Image(
                painter = painterResource(id = R.drawable.tap_here_nfc),
                contentDescription = "Tap here",
                modifier = Modifier.size(screenWidth * 0.39f),
                contentScale = ContentScale.Fit
            )

            Spacer(modifier = Modifier.height(screenHeight * 0.045f))

            Text(
                text = "TO PROCEED TO SCAN,\nTAP YOUR SCREEN",
                color = CueWhite,
                fontSize = 27.sp,
                lineHeight = 31.sp,
                fontFamily = KoulenFontFamily,
                textAlign = TextAlign.Center,
                letterSpacing = 0.sp
            )

            Spacer(modifier = Modifier.weight(1f))

            PinkActionButton(
                text = "EXIT CUE",
                modifier = Modifier.fillMaxWidth(0.62f),
                onClick = onExit
            )
        }
    }
}

@Composable
private fun WristbandScanningScreen(
    message: String?,
    onExit: () -> Unit,
    onBack: () -> Unit
) {
    WristbandScanStateScreen(
        complete = false,
        statusText = message ?: "once the wristband is scanned, a\ntick will appear on the page.",
        bottomButtonText = "BACK",
        onExit = onExit,
        onBottomClick = onBack
    )
}

@Composable
private fun WristbandCompleteScreen(
    onExit: () -> Unit,
    onDone: () -> Unit
) {
    WristbandScanStateScreen(
        complete = true,
        statusText = "once the wristband is scanned, a\ntick will appear on the page.",
        bottomButtonText = "DONE",
        onExit = onExit,
        onBottomClick = onDone
    )
}

@Composable
private fun WristbandScanStateScreen(
    complete: Boolean,
    statusText: String,
    bottomButtonText: String,
    onExit: () -> Unit,
    onBottomClick: () -> Unit
) {
    BoxWithConstraints(
        modifier = Modifier
            .fillMaxSize()
            .background(CueBlack)
            .statusBarsPadding()
            .navigationBarsPadding()
    ) {
        val screenWidth = maxWidth
        val screenHeight = maxHeight
        val horizontalInset = screenWidth * 0.08f
        val logoTop = screenHeight * 0.035f
        val closeSize = screenWidth * 0.09f

        HeaderLogoAndClose(
            screenWidth = screenWidth,
            logoWidth = screenWidth * 0.24f,
            horizontalInset = horizontalInset,
            top = logoTop,
            closeSize = closeSize,
            onExit = onExit
        )

        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(horizontal = horizontalInset)
                .padding(top = screenHeight * 0.20f, bottom = screenHeight * 0.08f),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .border(
                        width = 1.dp,
                        color = CueWhite,
                        shape = RoundedCornerShape(18.dp)
                    )
                    .padding(horizontal = 14.dp, vertical = 10.dp),
                contentAlignment = Alignment.Center
            ) {
                Text(
                    text = statusText,
                    color = CueMutedText,
                    fontSize = 16.sp,
                    lineHeight = 18.sp,
                    textAlign = TextAlign.Center
                )
            }

            Spacer(modifier = Modifier.height(screenHeight * 0.09f))

            Box(
                modifier = Modifier
                    .fillMaxWidth(0.70f)
                    .height(screenHeight * 0.30f),
                contentAlignment = Alignment.Center
            ) {
                WristbandOrb(complete = complete)
            }

            if (complete) {
                Spacer(modifier = Modifier.height(screenHeight * 0.055f))

                Box(
                    modifier = Modifier
                        .fillMaxWidth(0.52f)
                        .border(
                            width = 1.dp,
                            color = CueWhite,
                            shape = RoundedCornerShape(20.dp)
                        )
                        .padding(vertical = 8.dp),
                    contentAlignment = Alignment.Center
                ) {
                    Text(
                        text = "scanning complete",
                        color = CueMutedText,
                        fontSize = 15.sp,
                        textAlign = TextAlign.Center
                    )
                }
            }

            Spacer(modifier = Modifier.weight(1f))

            PinkActionButton(
                text = bottomButtonText,
                modifier = Modifier.fillMaxWidth(0.64f),
                onClick = onBottomClick
            )
        }
    }
}

@Composable
private fun WristbandOrb(
    complete: Boolean
) {
    Image(
        painter = painterResource(
            id = if (complete) {
                R.drawable.scan_wristband_complete_graphic
            } else {
                R.drawable.scan_wristband_graphic
            }
        ),
        contentDescription = if (complete) {
            "Wristband scanned"
        } else {
            "Scan your wristband"
        },
        modifier = Modifier.fillMaxSize(),
        contentScale = ContentScale.Fit
    )
}

@Composable
private fun PinkActionButton(
    text: String,
    modifier: Modifier,
    onClick: () -> Unit
) {
    Box(
        modifier = modifier
            .background(
                color = Color(0xFFFF9FD2),
                shape = RoundedCornerShape(50)
            )
            .clickable(onClick = onClick)
            .padding(vertical = 14.dp),
        contentAlignment = Alignment.Center
    ) {
        Text(
            text = text,
            color = CueBlack,
            fontSize = 18.sp,
            fontFamily = KoulenFontFamily,
            textAlign = TextAlign.Center,
            letterSpacing = 0.sp
        )
    }
}

@Composable
private fun IntroExplainerScreen(
    secondCardAlpha: Float,
    onAdvance: () -> Unit
) {
    BoxWithConstraints(
        modifier = Modifier
            .fillMaxSize()
            .background(CueBlack)
            .statusBarsPadding()
            .navigationBarsPadding()
    ) {
        val screenWidth = maxWidth
        val screenHeight = maxHeight
        val horizontalInset = screenWidth * 0.055f
        val logoTop = screenHeight * 0.035f
        val logoWidth = screenWidth * 0.24f
        val firstTextTop = screenHeight * 0.18f
        val cardTop = screenHeight * 0.50f
        val continueBottom = screenHeight * 0.105f

        WhiteCueLogo(
            modifier = Modifier
                .offset(
                    x = horizontalInset,
                    y = logoTop
                )
                .width(logoWidth)
        )

        Text(
            text = "ALL OUR CUE EVENTS HAVE\nHUBS \uD83D\uDCFA, WHICH HELP YOU\nSTART CONVERSATION \uD83D\uDC65\n\uD83D\uDCAC WITH YOUR POTENTIAL\nLOVER \uD83D\uDC96",
            modifier = Modifier
                .fillMaxWidth()
                .offset(y = firstTextTop)
                .padding(horizontal = screenWidth * 0.12f),
            color = CueWhite,
            fontSize = 27.sp,
            lineHeight = 35.sp,
            fontFamily = KoulenFontFamily,
            textAlign = TextAlign.Center,
            letterSpacing = 0.sp
        )

        Box(
            modifier = Modifier
                .fillMaxWidth(0.76f)
                .height(screenHeight * 0.19f)
                .align(Alignment.TopCenter)
                .offset(y = cardTop)
                .alpha(secondCardAlpha)
                .border(
                    width = 1.dp,
                    color = CueWhite,
                    shape = RoundedCornerShape(20.dp)
                )
                .padding(horizontal = 22.dp),
            contentAlignment = Alignment.Center
        ) {
            Text(
                text = "BUT HOW THE\nCONVERSATION STARTS\nIS UP TO YOU...",
                color = CueWhite,
                fontSize = 27.sp,
                lineHeight = 34.sp,
                fontFamily = KoulenFontFamily,
                textAlign = TextAlign.Center,
                letterSpacing = 0.sp
            )
        }

        Box(
            modifier = Modifier
                .fillMaxWidth(0.48f)
                .align(Alignment.BottomCenter)
                .offset(y = -continueBottom)
                .border(
                    width = 1.dp,
                    color = CueWhite,
                    shape = RoundedCornerShape(20.dp)
                )
                .clickable(onClick = onAdvance)
                .padding(vertical = 14.dp),
            contentAlignment = Alignment.Center
        ) {
            Text(
                text = "tap to continue",
                color = CueMutedText,
                fontSize = 20.sp,
                lineHeight = 22.sp,
                textAlign = TextAlign.Center,
                letterSpacing = 0.sp
            )
        }
    }
}

@Composable
private fun PersonaliseExperienceScreen(
    modifier: Modifier = Modifier,
    onExit: () -> Unit,
    onNext: () -> Unit
) {
    BoxWithConstraints(
        modifier = modifier
            .fillMaxSize()
            .background(CueBlack)
            .statusBarsPadding()
            .navigationBarsPadding()
    ) {
        val screenWidth = maxWidth
        val screenHeight = maxHeight
        val headerTop = screenHeight * 0.035f
        val horizontalInset = screenWidth * 0.08f
        val logoWidth = screenWidth * 0.24f
        val closeSize = screenWidth * 0.09f
        val titleTop = screenHeight * 0.155f
        val panelTop = screenHeight * 0.225f
        val panelHeight = screenHeight * 0.245f
        val skipTop = screenHeight * 0.68f

        WhiteCueLogo(
            modifier = Modifier
                .offset(
                    x = horizontalInset,
                    y = headerTop
                )
                .width(logoWidth)
        )

        CloseButton(
            modifier = Modifier
                .offset(
                    x = screenWidth - horizontalInset - closeSize,
                    y = headerTop
                )
                .size(closeSize),
            onClick = onExit
        )

        Text(
            text = "PERSONALISE YOUR\nEXPERIENCE",
            modifier = Modifier
                .fillMaxWidth()
                .offset(y = titleTop),
            color = CueWhite,
            fontSize = 29.sp,
            lineHeight = 31.sp,
            fontFamily = KoulenFontFamily,
            textAlign = TextAlign.Center,
            fontWeight = FontWeight.Bold,
            letterSpacing = 0.sp
        )

        CueMouthPanel(
            modifier = Modifier
                .fillMaxWidth()
                .height(panelHeight)
                .offset(y = panelTop),
            onClick = onNext
        )

        SkipButton(
            modifier = Modifier
                .fillMaxWidth(0.47f)
                .align(Alignment.TopCenter)
                .offset(y = skipTop),
            onClick = onExit
        )
    }
}

@Composable
private fun CueMouthPanel(
    modifier: Modifier = Modifier,
    onClick: () -> Unit
) {
    Box(
        modifier = modifier.clickable(onClick = onClick),
        contentAlignment = Alignment.Center
    ) {
        Canvas(
            modifier = Modifier.fillMaxSize()
        ) {
            val width = size.width
            val height = size.height

            val wave = Path().apply {
                moveTo(width * 0.0746f, 0f)
                lineTo(width * 0.0109f, 0f)
                lineTo(0f, height)
                lineTo(width * 0.9891f, height)
                lineTo(width, 0f)
                lineTo(width * 0.9337f, 0f)
                cubicTo(
                    width * 0.9337f,
                    0f,
                    width * 0.6814f,
                    height * 0.1571f,
                    width * 0.5067f,
                    height * 0.1578f
                )
                cubicTo(
                    width * 0.3301f,
                    height * 0.1585f,
                    width * 0.0746f,
                    0f,
                    width * 0.0746f,
                    0f
                )
                close()
            }

            drawPath(
                path = wave,
                brush = Brush.verticalGradient(
                    colorStops = arrayOf(
                        0f to SplashPink.copy(alpha = 0.72f),
                        0.18f to Color(0xA06B5864),
                        0.42f to Color(0x66231C22),
                        1f to Color(0x00000000)
                    ),
                    startY = 0f,
                    endY = height
                )
            )

            val mouth = Path().apply {
                moveTo(width * 0.20f, height * 0.64f)
                lineTo(width * 0.50f, height * 0.94f)
                lineTo(width * 0.80f, height * 0.64f)
            }

            drawPath(
                path = mouth,
                color = SplashPink,
                style = Stroke(
                    width = 10.dp.toPx(),
                    cap = StrokeCap.Round
                )
            )
        }
    }
}

@Composable
private fun CloseButton(
    modifier: Modifier = Modifier,
    onClick: () -> Unit
) {
    Box(
        modifier = modifier
            .background(
                color = SplashPink,
                shape = CircleShape
            )
            .clickable(
                onClick = onClick
            ),
        contentAlignment = Alignment.Center
    ) {
        Canvas(
            modifier = Modifier.size(18.dp)
        ) {
            drawLine(
                color = CueBlack,
                start = Offset.Zero,
                end = Offset(size.width, size.height),
                strokeWidth = 2.5.dp.toPx(),
                cap = StrokeCap.Round
            )
            drawLine(
                color = CueBlack,
                start = Offset(size.width, 0f),
                end = Offset(0f, size.height),
                strokeWidth = 2.5.dp.toPx(),
                cap = StrokeCap.Round
            )
        }
    }
}

@Composable
private fun SkipButton(
    modifier: Modifier = Modifier,
    onClick: () -> Unit
) {
    Box(
        modifier = modifier
            .border(
                width = 1.dp,
                color = CueWhite,
                shape = RoundedCornerShape(19.dp)
            )
            .clickable(onClick = onClick)
            .padding(horizontal = 18.dp, vertical = 10.dp),
        contentAlignment = Alignment.Center
    ) {
        Text(
            text = "Skip\n(complete at the venue)",
            color = CueMutedText,
            fontSize = 18.sp,
            lineHeight = 21.sp,
            textAlign = TextAlign.Center,
            letterSpacing = 0.sp
        )
    }
}

@Composable
private fun NextPlaceholderScreen(
    form: OnboardingFormState,
    errorMessage: String?,
    onExit: () -> Unit,
    onNext: () -> Unit
) {
    BoxWithConstraints(
        modifier = Modifier
            .fillMaxSize()
            .background(CueBlack)
            .statusBarsPadding()
            .navigationBarsPadding()
    ) {
        val screenWidth = maxWidth
        val screenHeight = maxHeight
        val headerTop = screenHeight * 0.035f
        val horizontalInset = screenWidth * 0.08f
        val logoWidth = screenWidth * 0.24f
        val closeSize = screenWidth * 0.09f

        Column(
            modifier = Modifier
                .fillMaxSize()
                .verticalScroll(rememberScrollState())
                .padding(horizontal = horizontalInset)
                .padding(
                    top = headerTop,
                    bottom = screenHeight * 0.18f
                )
        ) {
            WhiteCueLogo(
                modifier = Modifier.width(logoWidth)
            )

            Spacer(modifier = Modifier.height(screenHeight * 0.035f))

            NameQuestionBlock(form = form)

            SectionDivider()

            PronunciationQuestionBlock(form = form)

            Spacer(modifier = Modifier.height(screenHeight * 0.035f))

            IdentityQuestionBlock(form = form)

            SectionDivider()

            OrientationQuestionBlock(form = form)

            SectionDivider()

            AgeQuestionBlock(form = form)

            SectionDivider()

            AgeRangeQuestionBlock(form = form)

            SectionDivider()

            Spacer(modifier = Modifier.height(screenHeight * 0.035f))

            Text(
                text = "FILL OUT A NEXT SET\nOF QUESTION",
                modifier = Modifier.fillMaxWidth(),
                color = CueWhite,
                fontSize = 27.sp,
                lineHeight = 29.sp,
                fontFamily = KoulenFontFamily,
                textAlign = TextAlign.Center,
                letterSpacing = 0.sp
            )

            errorMessage?.let { message ->
                Spacer(modifier = Modifier.height(12.dp))
                BottomFormMessage(text = message)
            }

            CueMouthPanel(
                modifier = Modifier
                    .fillMaxWidth()
                    .height(screenHeight * 0.23f),
                onClick = onNext
            )
        }

        CloseButton(
            modifier = Modifier
                .offset(
                    x = screenWidth - horizontalInset - closeSize,
                    y = headerTop
                )
                .size(closeSize),
            onClick = onExit
        )

        FloatingSkipButton(
            modifier = Modifier
                .fillMaxWidth(0.50f)
                .align(Alignment.BottomCenter)
                .offset(y = -screenHeight * 0.085f),
            onClick = onExit
        )
    }
}

@Composable
private fun NameQuestionBlock(
    form: OnboardingFormState
) {
    SimpleTypedQuestion(
        title = "SO, WHAT'S YOUR NAME?",
        subtitle = "TYPICAL FIRST QUESTION",
        value = form.name,
        onValueChange = {
            form.name = it
        }
    )
}

@Composable
private fun PronunciationQuestionBlock(
    form: OnboardingFormState
) {
    QuestionTitle(
        text = "WOULD YOU LIKE IT TO BE\nPRONOUNCED A CERTAIN WAY?"
    )
    QuestionSubtitle(
        text = "OPTIONAL - SO THAT OUR HUB DOESN'T GIVE YOU THE ICK"
    )

    Spacer(modifier = Modifier.height(16.dp))

    PronunciationAudioCard(
        savedFileName = form.pronunciationFileName,
        onSaved = { file ->
            form.pronunciationFileName = file.name
            form.pronunciationFilePath = file.absolutePath
        }
    )
}

@Composable
private fun IdentityQuestionBlock(
    form: OnboardingFormState
) {
    QuestionTitle(text = "WHAT DO YOU IDENTIFY AS?")
    QuestionSubtitle(text = "SO WE CAN LET YOUR MATCHES KNOW")

    Spacer(modifier = Modifier.height(14.dp))

    ChoiceChips(
        labels = listOf("Male", "Female", "Other"),
        selectedLabel = form.identity,
        onSelectedChange = {
            form.identity = it
        }
    )

    Spacer(modifier = Modifier.height(12.dp))

    OtherInput(
        value = form.identityOther,
        onValueChange = {
            form.identityOther = it
        }
    )
}

@Composable
private fun OrientationQuestionBlock(
    form: OnboardingFormState
) {
    QuestionTitle(text = "WHAT'S YOUR SEXUAL\nORIENTATION?")
    QuestionSubtitle(text = "SO THAT WE DON'T MATCH THE GIRLS WITH THE GAYS")

    Spacer(modifier = Modifier.height(16.dp))

    TextWheel(
        value = form.orientation,
        options = listOf(
            "Heterosexual",
            "Homosexual",
            "Bisexual",
            "Pansexual"
        ),
        onValueChange = {
            form.orientation = it
            form.orientationOther = ""
        },
        modifier = Modifier.fillMaxWidth()
    )
}

@Composable
private fun AgeQuestionBlock(
    form: OnboardingFormState
) {
    QuestionTitle(text = "HOW OLD ARE YOU?")
    QuestionSubtitle(text = "DON'T FORGET YOUR ID'S")

    Spacer(modifier = Modifier.height(16.dp))

    Box(
        modifier = Modifier.fillMaxWidth(),
        contentAlignment = Alignment.Center
    ) {
        NumberWheel(
            value = form.age,
            range = 18..100,
            onValueChange = {
                form.age = it
            },
            modifier = Modifier.fillMaxWidth(0.36f)
        )
    }
}

@Composable
private fun AgeRangeQuestionBlock(
    form: OnboardingFormState
) {
    QuestionTitle(text = "AGE RANGE YOU WANT TO BE\nMATCHED WITH")
    QuestionSubtitle(text = "TO MAKE SURE EVERYTHING'S LEGAL")

    Spacer(modifier = Modifier.height(16.dp))

    Row(
        modifier = Modifier.fillMaxWidth(),
        verticalAlignment = Alignment.CenterVertically
    ) {
        NumberWheel(
            value = form.matchMinAge,
            range = 18..100,
            onValueChange = { nextMinAge ->
                form.matchMinAge = nextMinAge
                if (form.matchMaxAge < nextMinAge) {
                    form.matchMaxAge = nextMinAge
                }
            },
            modifier = Modifier.weight(1f)
        )

        Text(
            text = "-",
            modifier = Modifier.padding(horizontal = 18.dp),
            color = CueWhite,
            fontSize = 34.sp,
            lineHeight = 34.sp,
            textAlign = TextAlign.Center
        )

        NumberWheel(
            value = form.matchMaxAge,
            range = 18..100,
            onValueChange = { nextMaxAge ->
                form.matchMaxAge = nextMaxAge
                if (form.matchMinAge > nextMaxAge) {
                    form.matchMinAge = nextMaxAge
                }
            },
            modifier = Modifier.weight(1f)
        )
    }
}

@Composable
private fun NumberWheel(
    value: Int,
    range: IntRange,
    onValueChange: (Int) -> Unit,
    modifier: Modifier = Modifier
) {
    val values = remember(range.first, range.last) {
        range.toList()
    }
    val displayValues = remember(values) {
        listOf<Int?>(null) + values + listOf<Int?>(null)
    }
    val listState = rememberLazyListState(
        initialFirstVisibleItemIndex = (value - range.first).coerceIn(
            minimumValue = 0,
            maximumValue = values.lastIndex
        )
    )
    val coroutineScope = rememberCoroutineScope()

    LaunchedEffect(value, range.first, range.last) {
        val targetIndex = (value - range.first).coerceIn(
            minimumValue = 0,
            maximumValue = values.lastIndex
        )
        if (
            !listState.isScrollInProgress &&
            (
                listState.firstVisibleItemIndex != targetIndex ||
                    listState.firstVisibleItemScrollOffset != 0
                )
        ) {
            listState.animateScrollToItem(targetIndex)
        }
    }

    LaunchedEffect(listState, values) {
        snapshotFlow {
            listState.firstVisibleItemIndex to listState.firstVisibleItemScrollOffset
        }
            .distinctUntilChanged()
            .collect { (firstVisibleIndex, scrollOffset) ->
                val nearestFirstVisibleIndex = (
                    firstVisibleIndex + if (scrollOffset >= 21) {
                        1
                    } else {
                        0
                    }
                    ).coerceIn(
                    minimumValue = 0,
                    maximumValue = values.lastIndex
                )
                val selectedValue = values[nearestFirstVisibleIndex]
                if (selectedValue != value) {
                    onValueChange(selectedValue)
                }
            }
    }

    LaunchedEffect(listState, values) {
        snapshotFlow {
            listState.isScrollInProgress
        }
            .distinctUntilChanged()
            .collect { scrolling ->
                if (!scrolling) {
                    val targetIndex = (
                        listState.firstVisibleItemIndex +
                            if (listState.firstVisibleItemScrollOffset >= 21) {
                                1
                            } else {
                                0
                            }
                        ).coerceIn(
                        minimumValue = 0,
                        maximumValue = values.lastIndex
                    )
                    if (
                        listState.firstVisibleItemIndex != targetIndex ||
                        listState.firstVisibleItemScrollOffset != 0
                    ) {
                        listState.animateScrollToItem(targetIndex)
                    }
                }
            }
    }

    Box(
        modifier = modifier
            .height(126.dp)
            .border(
                width = 1.dp,
                color = CueWhite,
                shape = RoundedCornerShape(18.dp)
            )
    ) {
        LazyColumn(
            state = listState,
            modifier = Modifier.fillMaxSize(),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            itemsIndexed(displayValues) { index, number ->
                val selected = number == value
                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(42.dp)
                        .then(
                            if (number == null) {
                                Modifier
                            } else {
                                Modifier.clickable {
                                    onValueChange(number)
                                    coroutineScope.launch {
                                        listState.animateScrollToItem(
                                            (index - 1).coerceIn(
                                                minimumValue = 0,
                                                maximumValue = values.lastIndex
                                            )
                                        )
                                    }
                                }
                            }
                        ),
                    contentAlignment = Alignment.Center
                ) {
                    if (number != null) {
                        Text(
                            text = number.toString(),
                            color = if (selected) {
                                CueWhite
                            } else {
                                CueMutedText
                            },
                            fontSize = if (selected) {
                                28.sp
                            } else {
                                19.sp
                            },
                            lineHeight = 32.sp,
                            fontFamily = if (selected) {
                                KoulenFontFamily
                            } else {
                                null
                            },
                            textAlign = TextAlign.Center,
                            letterSpacing = 0.sp
                        )
                    }
                }
            }
        }

        Box(
            modifier = Modifier
                .align(Alignment.Center)
                .fillMaxWidth()
                .height(42.dp)
                .border(
                    width = 1.dp,
                    color = SplashPink.copy(alpha = 0.78f),
                    shape = RoundedCornerShape(14.dp)
                )
        )
    }
}

@Composable
private fun TextWheel(
    value: String,
    options: List<String>,
    onValueChange: (String) -> Unit,
    modifier: Modifier = Modifier
) {
    val displayOptions = remember(options) {
        listOf<String?>(null) + options + listOf<String?>(null)
    }
    val selectedIndex = options.indexOf(value).coerceAtLeast(0)
    val listState = rememberLazyListState(
        initialFirstVisibleItemIndex = selectedIndex
    )
    val coroutineScope = rememberCoroutineScope()

    LaunchedEffect(value, options) {
        val targetIndex = options.indexOf(value).coerceAtLeast(0)
        if (
            !listState.isScrollInProgress &&
            (
                listState.firstVisibleItemIndex != targetIndex ||
                    listState.firstVisibleItemScrollOffset != 0
                )
        ) {
            listState.animateScrollToItem(targetIndex)
        }
    }

    LaunchedEffect(listState, options) {
        snapshotFlow {
            listState.firstVisibleItemIndex to listState.firstVisibleItemScrollOffset
        }
            .distinctUntilChanged()
            .collect { (firstVisibleIndex, scrollOffset) ->
                val nearestIndex = (
                    firstVisibleIndex + if (scrollOffset >= 21) {
                        1
                    } else {
                        0
                    }
                    ).coerceIn(
                    minimumValue = 0,
                    maximumValue = options.lastIndex
                )
                val selectedValue = options[nearestIndex]
                if (selectedValue != value) {
                    onValueChange(selectedValue)
                }
            }
    }

    LaunchedEffect(listState, options) {
        snapshotFlow {
            listState.isScrollInProgress
        }
            .distinctUntilChanged()
            .collect { scrolling ->
                if (!scrolling) {
                    val targetIndex = (
                        listState.firstVisibleItemIndex +
                            if (listState.firstVisibleItemScrollOffset >= 21) {
                                1
                            } else {
                                0
                            }
                        ).coerceIn(
                        minimumValue = 0,
                        maximumValue = options.lastIndex
                    )
                    if (
                        listState.firstVisibleItemIndex != targetIndex ||
                        listState.firstVisibleItemScrollOffset != 0
                    ) {
                        listState.animateScrollToItem(targetIndex)
                    }
                }
            }
    }

    Box(
        modifier = modifier
            .height(126.dp)
            .border(
                width = 1.dp,
                color = CueWhite,
                shape = RoundedCornerShape(18.dp)
            )
    ) {
        LazyColumn(
            state = listState,
            modifier = Modifier.fillMaxSize(),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            itemsIndexed(displayOptions) { index, option ->
                val selected = option == value
                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(42.dp)
                        .then(
                            if (option == null) {
                                Modifier
                            } else {
                                Modifier.clickable {
                                    onValueChange(option)
                                    coroutineScope.launch {
                                        listState.animateScrollToItem(
                                            (index - 1).coerceIn(
                                                minimumValue = 0,
                                                maximumValue = options.lastIndex
                                            )
                                        )
                                    }
                                }
                            }
                        ),
                    contentAlignment = Alignment.Center
                ) {
                    if (option != null) {
                        Text(
                            text = option,
                            color = if (selected) {
                                CueWhite
                            } else {
                                CueMutedText
                            },
                            fontSize = if (selected) {
                                27.sp
                            } else {
                                19.sp
                            },
                            lineHeight = 32.sp,
                            fontFamily = if (selected) {
                                KoulenFontFamily
                            } else {
                                null
                            },
                            textAlign = TextAlign.Center,
                            letterSpacing = 0.sp
                        )
                    }
                }
            }
        }

        Box(
            modifier = Modifier
                .align(Alignment.Center)
                .fillMaxWidth()
                .height(42.dp)
                .border(
                    width = 1.dp,
                    color = SplashPink.copy(alpha = 0.78f),
                    shape = RoundedCornerShape(14.dp)
                )
        )
    }
}

@Composable
private fun SimpleTypedQuestion(
    title: String,
    subtitle: String,
    value: String,
    onValueChange: (String) -> Unit
) {
    QuestionTitle(text = title)
    QuestionSubtitle(text = subtitle)

    Spacer(modifier = Modifier.height(16.dp))

    SingleLineInput(
        value = value,
        onValueChange = onValueChange
    )
}

@Composable
private fun QuestionTitle(
    text: String
) {
    Text(
        text = text,
        color = CueWhite,
        fontSize = 28.sp,
        lineHeight = 30.sp,
        fontFamily = KoulenFontFamily,
        textAlign = TextAlign.Start,
        letterSpacing = 0.sp
    )
}

@Composable
private fun QuestionSubtitle(
    text: String
) {
    Text(
        text = text,
        color = SplashPink.copy(alpha = 0.78f),
        fontSize = 14.sp,
        lineHeight = 17.sp,
        fontFamily = KoulenFontFamily,
        letterSpacing = 0.sp
    )
}

@Composable
private fun SingleLineInput(
    value: String,
    onValueChange: (String) -> Unit
) {
    Box(
        modifier = Modifier
            .fillMaxWidth()
            .height(32.dp),
        contentAlignment = Alignment.BottomStart
    ) {
        BasicTextField(
            value = value,
            onValueChange = onValueChange,
            modifier = Modifier.fillMaxWidth(),
            textStyle = TextStyle(
                color = CueMutedText,
                fontSize = 17.sp,
                lineHeight = 20.sp
            ),
            cursorBrush = SolidColor(SplashPink),
            singleLine = true,
            decorationBox = { innerTextField ->
                Box {
                    if (value.isBlank()) {
                        Text(
                            text = "Type...",
                            color = CueMutedText,
                            fontSize = 17.sp
                        )
                    }
                    innerTextField()
                }
            }
        )

        Box(
            modifier = Modifier
                .fillMaxWidth()
                .height(1.dp)
                .background(CueWhite)
                .align(Alignment.BottomCenter)
        )
    }
}

@Composable
private fun OtherInput() {
    OtherInput(
        value = "",
        onValueChange = {}
    )
}

@Composable
private fun OtherInput(
    value: String,
    onValueChange: (String) -> Unit
) {
    Text(
        text = "Other:",
        color = CueMutedText,
        fontSize = 16.sp,
        fontWeight = FontWeight.Bold
    )
    SingleLineInput(
        value = value,
        onValueChange = onValueChange
    )
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun ChoiceChips(
    labels: List<String>,
    selectedLabel: String?,
    onSelectedChange: (String?) -> Unit
) {
    FlowRow(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = androidx.compose.foundation.layout.Arrangement.spacedBy(16.dp),
        verticalArrangement = androidx.compose.foundation.layout.Arrangement.spacedBy(10.dp)
    ) {
        labels.forEach { label ->
            val selected = selectedLabel == label
            Box(
                modifier = Modifier
                    .width(98.dp)
                    .background(
                        color = if (selected) {
                            CueSelectedChip
                        } else {
                            Color.Transparent
                        },
                        shape = RoundedCornerShape(50)
                    )
                    .border(
                        width = 1.dp,
                        color = CueWhite,
                        shape = RoundedCornerShape(50)
                    )
                    .clickable {
                        onSelectedChange(if (selected) {
                            null
                        } else {
                            label
                        })
                    }
                    .padding(vertical = 8.dp),
                contentAlignment = Alignment.Center
            ) {
                Text(
                    text = label,
                    color = if (selected) {
                        CueWhite
                    } else {
                        CueMutedText
                    },
                    fontSize = 16.sp,
                    lineHeight = 18.sp,
                    textAlign = TextAlign.Center
                )
            }
        }
    }
}

@Composable
private fun PronunciationAudioCard(
    savedFileName: String?,
    onSaved: (File) -> Unit
) {
    val context = LocalContext.current
    val recorder = remember {
        PronunciationRecorder(context.applicationContext)
    }
    var isRecording by remember {
        mutableStateOf(false)
    }
    var recordingError by remember {
        mutableStateOf<String?>(null)
    }
    val permissionLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.RequestPermission()
    ) { granted ->
        if (granted) {
            runCatching {
                recorder.start()
            }.onSuccess {
                isRecording = true
                recordingError = null
            }.onFailure {
                isRecording = false
                recordingError = "Could not start recording."
            }
        } else {
            recordingError = "Microphone permission is needed to record."
        }
    }

    DisposableEffect(Unit) {
        onDispose {
            if (isRecording) {
                recorder.stop()
            } else {
                recorder.release()
            }
        }
    }

    fun toggleRecording() {
        if (isRecording) {
            val savedFile = recorder.stop()
            isRecording = false
            if (savedFile == null) {
                recordingError = "Recording was too short. Try again."
            } else {
                onSaved(savedFile)
                recordingError = null
            }
            return
        }

        val permissionGranted = ContextCompat.checkSelfPermission(
            context,
            Manifest.permission.RECORD_AUDIO
        ) == PackageManager.PERMISSION_GRANTED

        if (permissionGranted) {
            runCatching {
                recorder.start()
            }.onSuccess {
                isRecording = true
                recordingError = null
            }.onFailure {
                isRecording = false
                recordingError = "Could not start recording."
            }
        } else {
            permissionLauncher.launch(Manifest.permission.RECORD_AUDIO)
        }
    }

    Box(
        modifier = Modifier
            .fillMaxWidth()
            .background(
                color = if (isRecording) {
                    SplashPink.copy(alpha = 0.10f)
                } else {
                    Color.Transparent
                },
                shape = RoundedCornerShape(22.dp)
            )
            .border(
                width = 1.dp,
                color = if (isRecording) {
                    SplashPink
                } else {
                    CueWhite
                },
                shape = RoundedCornerShape(22.dp)
            )
            .clickable {
                toggleRecording()
            }
            .padding(horizontal = 16.dp, vertical = 14.dp)
    ) {
        Column {
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically
            ) {
                Box(
                    modifier = Modifier
                        .size(54.dp)
                        .background(
                            color = if (isRecording) {
                                SplashPink
                            } else {
                                Color.Transparent
                            },
                            shape = CircleShape
                        )
                        .border(
                            width = 1.dp,
                            color = SplashPink,
                            shape = CircleShape
                        ),
                    contentAlignment = Alignment.Center
                ) {
                    Canvas(modifier = Modifier.size(20.dp)) {
                        if (isRecording) {
                            drawRoundRect(
                                color = CueBlack,
                                size = androidx.compose.ui.geometry.Size(
                                    width = size.width,
                                    height = size.height
                                ),
                                cornerRadius = androidx.compose.ui.geometry.CornerRadius(
                                    x = 3.dp.toPx(),
                                    y = 3.dp.toPx()
                                )
                            )
                        } else {
                            drawCircle(
                                color = SplashPink,
                                radius = size.minDimension / 2f
                            )
                        }
                    }
                }

                Spacer(modifier = Modifier.width(14.dp))

                Column(modifier = Modifier.weight(1f)) {
                    Text(
                        text = when {
                            isRecording -> "Recording pronunciation"
                            savedFileName != null -> "Pronunciation saved"
                            else -> "Record pronunciation"
                        },
                        color = CueWhite,
                        fontSize = 18.sp,
                        lineHeight = 21.sp
                    )
                    Text(
                        text = when {
                            isRecording -> "Tap again to stop and save"
                            savedFileName != null -> "Optional - tap to record again"
                            else -> "Optional - tap to start"
                        },
                        color = CueMutedText,
                        fontSize = 14.sp,
                        lineHeight = 17.sp
                    )
                }

                Text(
                    text = if (isRecording) {
                        "REC"
                    } else {
                        "M4A"
                    },
                    color = if (isRecording) {
                        SplashPink
                    } else {
                        CueMutedText
                    },
                    fontSize = 14.sp,
                    lineHeight = 16.sp,
                    fontFamily = KoulenFontFamily,
                    letterSpacing = 0.sp
                )
            }

            recordingError?.let { message ->
                Spacer(modifier = Modifier.height(10.dp))
                Text(
                    text = message,
                    color = SplashPink,
                    fontSize = 13.sp,
                    lineHeight = 15.sp
                )
            }
        }
    }
}

@Composable
private fun RowLikeAudioInput(
    savedFileName: String?,
    onSaved: (File) -> Unit
) {
    val context = LocalContext.current
    val recorder = remember {
        PronunciationRecorder(context.applicationContext)
    }
    var isRecording by remember {
        mutableStateOf(false)
    }
    var recordingError by remember {
        mutableStateOf<String?>(null)
    }
    val permissionLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.RequestPermission()
    ) { granted ->
        if (granted) {
            runCatching {
                recorder.start()
            }.onSuccess {
                isRecording = true
                recordingError = null
            }.onFailure {
                isRecording = false
                recordingError = "Could not start recording."
            }
        } else {
            recordingError = "Microphone permission is needed to record."
        }
    }

    DisposableEffect(Unit) {
        onDispose {
            if (isRecording) {
                recorder.stop()
            } else {
                recorder.release()
            }
        }
    }

    fun toggleRecording() {
        if (isRecording) {
            val savedFile = recorder.stop()
            isRecording = false
            if (savedFile == null) {
                recordingError = "Recording was too short. Try again."
            } else {
                onSaved(savedFile)
                recordingError = null
            }
            return
        }

        val permissionGranted = ContextCompat.checkSelfPermission(
            context,
            Manifest.permission.RECORD_AUDIO
        ) == PackageManager.PERMISSION_GRANTED

        if (permissionGranted) {
            runCatching {
                recorder.start()
            }.onSuccess {
                isRecording = true
                recordingError = null
            }.onFailure {
                isRecording = false
                recordingError = "Could not start recording."
            }
        } else {
            permissionLauncher.launch(Manifest.permission.RECORD_AUDIO)
        }
    }

    Row(
        modifier = Modifier.fillMaxWidth(),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Box(
            modifier = Modifier
                .weight(1f)
                .border(
                    width = 1.dp,
                    color = CueWhite,
                    shape = RoundedCornerShape(50)
                )
                .clickable {
                    toggleRecording()
                }
                .padding(horizontal = 14.dp, vertical = 8.dp),
            contentAlignment = Alignment.Center
        ) {
            Text(
                text = when {
                    isRecording -> "Recording... tap to stop"
                    savedFileName != null -> "Saved pronunciation"
                    else -> "Record a pronunciation"
                },
                color = if (isRecording) {
                    SplashPink
                } else {
                    CueMutedText
                },
                fontSize = 16.sp
            )
        }

        Spacer(modifier = Modifier.width(14.dp))

        Text(
            text = if (isRecording) {
                "REC"
            } else {
                "♪"
            },
            color = if (isRecording) {
                SplashPink
            } else {
                CueWhite
            },
            fontSize = if (isRecording) {
                18.sp
            } else {
                34.sp
            },
            lineHeight = 34.sp
        )
    }

    savedFileName?.let { fileName ->
        Spacer(modifier = Modifier.height(8.dp))
        Text(
            text = "Saved locally: $fileName",
            color = CueMutedText,
            fontSize = 13.sp,
            lineHeight = 15.sp
        )
    }

    recordingError?.let { message ->
        Spacer(modifier = Modifier.height(8.dp))
        Text(
            text = message,
            color = SplashPink,
            fontSize = 13.sp,
            lineHeight = 15.sp
        )
    }

    Spacer(modifier = Modifier.height(15.dp))

    AudioWaveform(active = isRecording)
}

@Composable
private fun RowLikeAudioInputOld() {
    Row(
        modifier = Modifier.fillMaxWidth(),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Box(
            modifier = Modifier
                .weight(1f)
                .border(
                    width = 1.dp,
                    color = CueWhite,
                    shape = RoundedCornerShape(50)
                )
                .padding(horizontal = 14.dp, vertical = 8.dp),
            contentAlignment = Alignment.Center
        ) {
            Text(
                text = "Record a pronunciation",
                color = CueMutedText,
                fontSize = 16.sp
            )
        }

        Spacer(modifier = Modifier.width(14.dp))

        Text(
            text = "♩",
            color = CueWhite,
            fontSize = 34.sp,
            lineHeight = 34.sp
        )
    }

    Spacer(modifier = Modifier.height(15.dp))

    AudioWaveform()
}

@Composable
private fun AudioWaveform(
    active: Boolean
) {
    Canvas(
        modifier = Modifier
            .fillMaxWidth(0.86f)
            .height(28.dp)
    ) {
        val bars = 54
        val gap = size.width / (bars * 1.8f)
        val barWidth = gap * 0.45f
        repeat(bars) { index ->
            val normal = (index % 7 + 2) / 9f
            val height = size.height * (0.25f + normal * 0.65f)
            val x = index * gap
            drawLine(
                color = if (active) {
                    SplashPink
                } else {
                    CueMutedText
                },
                start = Offset(x, size.height / 2f - height / 2f),
                end = Offset(x, size.height / 2f + height / 2f),
                strokeWidth = barWidth,
                cap = StrokeCap.Round
            )
        }
    }
}

@Composable
private fun AudioWaveform() {
    Canvas(
        modifier = Modifier
            .fillMaxWidth(0.86f)
            .height(28.dp)
    ) {
        val bars = 54
        val gap = size.width / (bars * 1.8f)
        val barWidth = gap * 0.45f
        repeat(bars) { index ->
            val normal = (index % 7 + 2) / 9f
            val height = size.height * (0.25f + normal * 0.65f)
            val x = index * gap
            drawLine(
                color = CueMutedText,
                start = Offset(x, size.height / 2f - height / 2f),
                end = Offset(x, size.height / 2f + height / 2f),
                strokeWidth = barWidth,
                cap = StrokeCap.Round
            )
        }
    }
}

@Composable
private fun SectionDivider() {
    Spacer(modifier = Modifier.height(36.dp))
}

@Composable
private fun FloatingSkipButton(
    modifier: Modifier = Modifier,
    onClick: () -> Unit
) {
    Box(
        modifier = modifier
            .background(
                color = Color(0xFFFF9FD2),
                shape = RoundedCornerShape(50)
            )
            .clickable(onClick = onClick)
            .padding(vertical = 14.dp),
        contentAlignment = Alignment.Center
    ) {
        Text(
            text = "SKIP",
            color = CueBlack,
            fontSize = 18.sp,
            fontFamily = KoulenFontFamily,
            textAlign = TextAlign.Center,
            letterSpacing = 0.sp
        )
    }
}

@Composable
private fun HubCueQuestionScreen(
    form: OnboardingFormState,
    message: String?,
    uploadInProgress: Boolean,
    onExit: () -> Unit,
    onBack: () -> Unit
) {
    BoxWithConstraints(
        modifier = Modifier
            .fillMaxSize()
            .background(CueBlack)
            .statusBarsPadding()
            .navigationBarsPadding()
    ) {
        val screenWidth = maxWidth
        val screenHeight = maxHeight
        val headerTop = screenHeight * 0.035f
        val horizontalInset = screenWidth * 0.08f
        val logoWidth = screenWidth * 0.24f
        val closeSize = screenWidth * 0.09f
        var soundCloudSearchOpen by remember {
            mutableStateOf(false)
        }
        var soundCloudUrl by remember {
            mutableStateOf("")
        }
        var soundCloudUrlLoading by remember {
            mutableStateOf(false)
        }
        var soundCloudUrlError by remember {
            mutableStateOf<String?>(null)
        }
        val coroutineScope = rememberCoroutineScope()

        Column(
            modifier = Modifier
                .fillMaxSize()
                .verticalScroll(rememberScrollState())
                .padding(horizontal = horizontalInset)
                .padding(
                    top = headerTop,
                    bottom = screenHeight * 0.18f
                )
        ) {
            WhiteCueLogo(
                modifier = Modifier.width(logoWidth)
            )

            Spacer(modifier = Modifier.height(screenHeight * 0.035f))

            BigMutedCopy(
                text = "WHEN OUR HUB FINDS YOU A\nMATCH, IT NEEDS TO LET YOU\nKNOW"
            )

            Spacer(modifier = Modifier.height(screenHeight * 0.035f))

            QuestionTitle(
                text = "HOW DO YOU WANT OUR HUB TO\nCUE YOU?*"
            )

            Spacer(modifier = Modifier.height(18.dp))

            SelectableFullWidthOption(
                text = "play a song that only I know I've\npicked, on the venue speakers",
                selected = form.cueChoice == "song",
                onClick = {
                    form.cueChoice = "song"
                }
            )

            Spacer(modifier = Modifier.height(12.dp))

            SelectableFullWidthOption(
                text = "I want it to cue me, only by calling\nout the names of me and my match",
                selected = form.cueChoice == "names",
                onClick = {
                    form.cueChoice = "names"
                }
            )

            Spacer(modifier = Modifier.height(12.dp))

            SelectableFullWidthOption(
                text = "either!",
                selected = form.cueChoice == "either!",
                onClick = {
                    form.cueChoice = "either!"
                }
            )

            Spacer(modifier = Modifier.height(screenHeight * 0.035f))

            BigMutedCopy(
                text = "AFTER BEING MATCHED, THE\nBOTH OF YOU MUST SCAN YOUR\nWRISTBANDS AT THE NEAREST\nHUB"
            )

            Spacer(modifier = Modifier.height(screenHeight * 0.03f))

            QuestionTitle(
                text = "WHEN I'M MATCHED, I WANT*"
            )

            Spacer(modifier = Modifier.height(18.dp))

            SelectableOptionGroup(
                options = listOf(
                    "no help at all, I'll steer the convo",
                    "to be given a small ice breaker",
                    "play a short game together, on\nthe hub",
                    "play a longer game on the hub"
                ),
                selected = form.matchedPreference,
                onSelectedChange = {
                    form.matchedPreference = it
                }
            )

            if (form.cueChoice == "song" || form.cueChoice == "either!") {
                Spacer(modifier = Modifier.height(screenHeight * 0.04f))

                BigMutedCopy(
                    text = "WHICH SONG WOULD YOU\nRECOGNISE NO MATTER WHAT"
                )

                Spacer(modifier = Modifier.height(screenHeight * 0.025f))

                QuestionTitle(
                    text = "WE'LL USE THIS SONG AS A\nCUE*"
                )

                Spacer(modifier = Modifier.height(18.dp))

                SongInput(
                    selectedTrack = form.selectedTrack,
                    onClick = {
                        soundCloudSearchOpen = true
                    }
                )

                Spacer(modifier = Modifier.height(14.dp))

                SoundCloudUrlInput(
                    value = soundCloudUrl,
                    loading = soundCloudUrlLoading,
                    errorMessage = soundCloudUrlError,
                    onValueChange = {
                        soundCloudUrl = it
                        soundCloudUrlError = null
                    },
                    onSubmit = {
                        val pastedUrl = soundCloudUrl.trim()

                        if (pastedUrl.isBlank()) {
                            soundCloudUrlError = "Paste a SoundCloud song link."
                            return@SoundCloudUrlInput
                        }

                        coroutineScope.launch {
                            soundCloudUrlLoading = true
                            soundCloudUrlError = null

                            SoundCloudApiClient.searchTracks(pastedUrl)
                                .onSuccess { tracks ->
                                    val track = tracks.firstOrNull()

                                    if (track == null) {
                                        soundCloudUrlError = "Could not read that SoundCloud link."
                                    } else {
                                        form.selectedTrack = track
                                        soundCloudUrl = track.url
                                    }
                                }
                                .onFailure { error ->
                                    soundCloudUrlError = error.message ?: "Could not read that SoundCloud link."
                                }

                            soundCloudUrlLoading = false
                        }
                    }
                )
            }

            Spacer(modifier = Modifier.height(screenHeight * 0.045f))

            BigMutedCopy(
                text = "AFTER THE EVENT, (OR DURING\nBY TAPPING YOUR WRISTBAND)\nYOU CAN SHARE SOCIALS, IF\nYOU ENJOYED THE INTERACTION"
            )

            Spacer(modifier = Modifier.height(screenHeight * 0.025f))

            QuestionTitle(text = "SOCIALS: OPTIONAL")

            Spacer(modifier = Modifier.height(18.dp))

            SocialInput(
                iconResource = R.drawable.instagram_logo,
                placeholder = "Type your ins...",
                value = form.instagram,
                onValueChange = {
                    form.instagram = it
                }
            )
            SocialInput(
                iconResource = R.drawable.snapchat_logo,
                placeholder = "Type your snap...",
                value = form.snapchat,
                onValueChange = {
                    form.snapchat = it
                }
            )
            SocialInput(
                iconResource = R.drawable.whatsapp_logo,
                placeholder = "Type your number...",
                value = form.whatsapp,
                onValueChange = {
                    form.whatsapp = it
                }
            )

            message?.let { text ->
                Spacer(modifier = Modifier.height(18.dp))
                BottomFormMessage(text = text)
            }
        }

        CloseButton(
            modifier = Modifier
                .offset(
                    x = screenWidth - horizontalInset - closeSize,
                    y = headerTop
                )
                .size(closeSize),
            onClick = onExit
        )

        FloatingBackButton(
            text = "FINISH",
            modifier = Modifier
                .fillMaxWidth(0.50f)
                .align(Alignment.BottomCenter)
                .offset(y = -screenHeight * 0.085f),
            onClick = {
                if (!uploadInProgress) {
                    onBack()
                }
            }
        )

        if (soundCloudSearchOpen) {
            SoundCloudSearchOverlay(
                onDismiss = {
                    soundCloudSearchOpen = false
                },
                onTrackSelected = { track ->
                    form.selectedTrack = track
                    soundCloudSearchOpen = false
                }
            )
        }
    }
}

@Composable
private fun BigMutedCopy(
    text: String
) {
    Text(
        text = text,
        color = CueMutedText,
        fontSize = 27.sp,
        lineHeight = 30.sp,
        fontFamily = KoulenFontFamily,
        letterSpacing = 0.sp
    )
}

@Composable
private fun SelectableOptionGroup(
    options: List<String>,
    selected: String?,
    onSelectedChange: (String?) -> Unit
) {
    options.forEachIndexed { index, option ->
        if (index > 0) {
            Spacer(modifier = Modifier.height(12.dp))
        }

        SelectableFullWidthOption(
            text = option,
            selected = selected == option,
            onClick = {
                onSelectedChange(if (selected == option) {
                    null
                } else {
                    option
                })
            }
        )
    }
}

@Composable
private fun SelectableFullWidthOption(
    text: String,
    selected: Boolean,
    onClick: () -> Unit
) {
    Box(
        modifier = Modifier
            .fillMaxWidth()
            .background(
                color = if (selected) {
                    CueSelectedChip
                } else {
                    Color.Transparent
                },
                shape = RoundedCornerShape(50)
            )
            .border(
                width = 1.dp,
                color = CueWhite,
                shape = RoundedCornerShape(50)
            )
            .clickable(onClick = onClick)
            .padding(horizontal = 16.dp, vertical = 10.dp),
        contentAlignment = Alignment.Center
    ) {
        Text(
            text = text,
            color = if (selected) {
                CueWhite
            } else {
                CueMutedText
            },
            fontSize = 16.sp,
            lineHeight = 18.sp,
            textAlign = TextAlign.Center
        )
    }
}

@Composable
private fun SongInput(
    selectedTrack: SoundCloudTrack?,
    onClick: () -> Unit
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .border(
                width = 1.dp,
                color = CueWhite,
                shape = RoundedCornerShape(50)
            )
            .clickable(onClick = onClick)
            .padding(horizontal = 14.dp, vertical = 8.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Text(
            text = selectedTrack?.let {
                "${it.title} - ${it.artists}"
            } ?: "Type in a Song...",
            modifier = Modifier.weight(1f),
            color = if (selectedTrack == null) {
                CueMutedText
            } else {
                CueWhite
            },
            fontSize = 16.sp
        )
        SoundCloudBadge(size = 24.dp)
    }
}

@Composable
private fun SoundCloudUrlInput(
    value: String,
    loading: Boolean,
    errorMessage: String?,
    onValueChange: (String) -> Unit,
    onSubmit: () -> Unit
) {
    Column {
        Row(
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically
        ) {
            SoundCloudBadge(
                size = 56.dp
            )

            Spacer(modifier = Modifier.width(16.dp))

            Box(
                modifier = Modifier
                    .weight(1f)
                    .background(
                        color = Color(0xFF343434),
                        shape = RoundedCornerShape(50)
                    )
                    .border(
                        width = 1.dp,
                        color = CueWhite,
                        shape = RoundedCornerShape(50)
                    )
                    .padding(horizontal = 16.dp, vertical = 12.dp)
            ) {
                BasicTextField(
                    value = value,
                    onValueChange = onValueChange,
                    modifier = Modifier.fillMaxWidth(),
                    textStyle = TextStyle(
                        color = CueWhite,
                        fontSize = 15.sp,
                        lineHeight = 18.sp,
                        textAlign = TextAlign.Center
                    ),
                    cursorBrush = SolidColor(SplashPink),
                    singleLine = true,
                    decorationBox = { innerTextField ->
                        Box(
                            modifier = Modifier.fillMaxWidth(),
                            contentAlignment = Alignment.Center
                        ) {
                            if (value.isBlank()) {
                                Text(
                                    text = "Paste SoundCloud song link",
                                    color = CueMutedText,
                                    fontSize = 15.sp,
                                    lineHeight = 18.sp,
                                    textAlign = TextAlign.Center
                                )
                            }
                            innerTextField()
                        }
                    }
                )
            }

            Spacer(modifier = Modifier.width(10.dp))

            Box(
                modifier = Modifier
                    .background(
                        color = if (loading) {
                            CueSelectedChip
                        } else {
                            SplashPink
                        },
                        shape = RoundedCornerShape(50)
                    )
                    .clickable(
                        enabled = !loading,
                        onClick = onSubmit
                    )
                    .padding(horizontal = 16.dp, vertical = 12.dp),
                contentAlignment = Alignment.Center
            ) {
                Text(
                    text = if (loading) {
                        "..."
                    } else {
                        "ADD"
                    },
                    color = CueBlack,
                    fontSize = 16.sp,
                    lineHeight = 18.sp,
                    fontFamily = KoulenFontFamily,
                    letterSpacing = 0.sp
                )
            }
        }

        errorMessage?.let { message ->
            Spacer(modifier = Modifier.height(8.dp))
            Text(
                text = message,
                color = SplashPink,
                fontSize = 14.sp,
                lineHeight = 17.sp,
                textAlign = TextAlign.Center,
                modifier = Modifier.fillMaxWidth()
            )
        }
    }
}

@Composable
private fun SoundCloudSearchOverlay(
    onDismiss: () -> Unit,
    onTrackSelected: (SoundCloudTrack) -> Unit
) {
    var query by remember {
        mutableStateOf("")
    }
    var tracks by remember {
        mutableStateOf<List<SoundCloudTrack>>(emptyList())
    }
    var loading by remember {
        mutableStateOf(false)
    }
    var errorMessage by remember {
        mutableStateOf<String?>(null)
    }

    LaunchedEffect(query) {
        val trimmedQuery = query.trim()
        if (trimmedQuery.length < 2) {
            tracks = emptyList()
            loading = false
            errorMessage = null
            return@LaunchedEffect
        }

        delay(350)
        loading = true
        errorMessage = null

        val result = SoundCloudApiClient.searchTracks(trimmedQuery)
        result
            .onSuccess { searchResults ->
                tracks = searchResults
            }
            .onFailure { error ->
                tracks = emptyList()
                errorMessage = error.message ?: "Could not search SoundCloud."
        }

        loading = false
    }

    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(CueBlack.copy(alpha = 0.96f))
            .statusBarsPadding()
            .navigationBarsPadding()
            .padding(horizontal = 30.dp, vertical = 28.dp)
    ) {
        Column(
            modifier = Modifier.fillMaxSize()
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically
            ) {
                SoundCloudBadge(size = 44.dp)

                Spacer(modifier = Modifier.width(14.dp))

                Text(
                    text = "FIND YOUR SONG",
                    modifier = Modifier.weight(1f),
                    color = CueWhite,
                    fontSize = 28.sp,
                    lineHeight = 30.sp,
                    fontFamily = KoulenFontFamily,
                    letterSpacing = 0.sp
                )

                Text(
                    text = "×",
                    modifier = Modifier.clickable(onClick = onDismiss),
                    color = SplashPink,
                    fontSize = 38.sp,
                    lineHeight = 38.sp
                )
            }

            Spacer(modifier = Modifier.height(28.dp))

            SoundCloudSearchField(
                value = query,
                onValueChange = {
                    query = it
                }
            )

            Spacer(modifier = Modifier.height(22.dp))

            Text(
                text = "SEARCH RESULTS",
                color = SplashPink.copy(alpha = 0.78f),
                fontSize = 16.sp,
                lineHeight = 18.sp,
                fontFamily = KoulenFontFamily,
                letterSpacing = 0.sp
            )

            Spacer(modifier = Modifier.height(14.dp))

            Column(
                modifier = Modifier.verticalScroll(rememberScrollState())
            ) {
                if (query.trim().length < 2) {
                    Text(
                        text = "Type at least two letters to search SoundCloud.",
                        color = CueMutedText,
                        fontSize = 17.sp,
                        lineHeight = 20.sp
                    )
                }

                if (loading) {
                    Text(
                        text = "Searching SoundCloud...",
                        color = CueMutedText,
                        fontSize = 17.sp,
                        lineHeight = 20.sp
                    )
                }

                errorMessage?.let { message ->
                    Text(
                        text = message,
                        color = SplashPink,
                        fontSize = 16.sp,
                        lineHeight = 19.sp
                    )
                }

                tracks.forEach { track ->
                    SoundCloudTrackRow(
                        track = track,
                        onClick = {
                            onTrackSelected(track)
                        }
                    )
                }

                if (
                    !loading &&
                    errorMessage == null &&
                    query.trim().length >= 2 &&
                    tracks.isEmpty()
                ) {
                    Text(
                        text = "No songs found yet.",
                        color = CueMutedText,
                        fontSize = 17.sp,
                        lineHeight = 20.sp
                    )
                }
            }
        }
    }
}

@Composable
private fun SoundCloudSearchField(
    value: String,
    onValueChange: (String) -> Unit
) {
    Box(
        modifier = Modifier
            .fillMaxWidth()
            .border(
                width = 1.dp,
                color = CueWhite,
                shape = RoundedCornerShape(50)
            )
            .padding(horizontal = 18.dp, vertical = 12.dp)
    ) {
        BasicTextField(
            value = value,
            onValueChange = onValueChange,
            modifier = Modifier.fillMaxWidth(),
            textStyle = TextStyle(
                color = CueWhite,
                fontSize = 18.sp,
                lineHeight = 21.sp
            ),
            cursorBrush = SolidColor(SplashPink),
            singleLine = true,
            decorationBox = { innerTextField ->
                Box {
                    if (value.isBlank()) {
                        Text(
                            text = "Search SoundCloud...",
                            color = CueMutedText,
                            fontSize = 18.sp
                        )
                    }
                    innerTextField()
                }
            }
        )
    }
}

@Composable
private fun SoundCloudTrackRow(
    track: SoundCloudTrack,
    onClick: () -> Unit
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick)
            .padding(vertical = 12.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Box(
            modifier = Modifier
                .size(54.dp)
                .background(
                    brush = Brush.linearGradient(
                        colors = listOf(
                            SplashPink,
                            CueSelectedChip,
                            Color(0xFF1ED760)
                        )
                    ),
                    shape = RoundedCornerShape(8.dp)
                ),
            contentAlignment = Alignment.Center
        ) {
            SoundCloudBadge(size = 28.dp)
        }

        Spacer(modifier = Modifier.width(14.dp))

        Column(
            modifier = Modifier.weight(1f)
        ) {
            Text(
                text = track.title,
                color = CueWhite,
                fontSize = 18.sp,
                lineHeight = 21.sp
            )
            Text(
                text = track.artists,
                color = CueMutedText,
                fontSize = 15.sp,
                lineHeight = 18.sp
            )
            Text(
                text = track.album,
                color = CueMutedText.copy(alpha = 0.75f),
                fontSize = 13.sp,
                lineHeight = 16.sp
            )
        }
    }
}

@Composable
private fun SoundCloudBadge(
    size: androidx.compose.ui.unit.Dp
) {
    Image(
        painter = painterResource(id = R.drawable.soundcloud_logo),
        contentDescription = "SoundCloud",
        modifier = Modifier
            .size(size),
        contentScale = ContentScale.Fit
    )
}

@Composable
private fun SocialInput(
    iconResource: Int,
    placeholder: String,
    value: String,
    onValueChange: (String) -> Unit
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(bottom = 18.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Image(
            painter = painterResource(id = iconResource),
            contentDescription = null,
            modifier = Modifier.size(42.dp),
            contentScale = ContentScale.Fit
        )

        Spacer(modifier = Modifier.width(14.dp))

        BasicTextField(
            value = value,
            onValueChange = onValueChange,
            modifier = Modifier.weight(1f),
            textStyle = TextStyle(
                color = CueMutedText,
                fontSize = 16.sp,
                lineHeight = 19.sp
            ),
            cursorBrush = SolidColor(SplashPink),
            singleLine = true,
            decorationBox = { innerTextField ->
                Box {
                    if (value.isBlank()) {
                        Text(
                            text = placeholder,
                            color = CueMutedText,
                            fontSize = 16.sp
                        )
                    }
                    innerTextField()
                }
            }
        )
    }
}

@Composable
private fun BottomFormMessage(
    text: String
) {
    Text(
        text = text,
        modifier = Modifier.fillMaxWidth(),
        color = SplashPink,
        fontSize = 15.sp,
        lineHeight = 18.sp,
        textAlign = TextAlign.Center,
        letterSpacing = 0.sp
    )
}

@Composable
private fun FloatingBackButton(
    text: String = "BACK",
    modifier: Modifier = Modifier,
    onClick: () -> Unit
) {
    Box(
        modifier = modifier
            .background(
                color = Color(0xFFFF9FD2),
                shape = RoundedCornerShape(50)
            )
            .clickable(onClick = onClick)
            .padding(vertical = 14.dp),
        contentAlignment = Alignment.Center
    ) {
        Text(
            text = text,
            color = CueBlack,
            fontSize = 18.sp,
            fontFamily = KoulenFontFamily,
            textAlign = TextAlign.Center,
            letterSpacing = 0.sp
        )
    }
}

@Composable
private fun WhiteCueLogo(
    modifier: Modifier = Modifier
) {
    Image(
        painter = painterResource(id = R.drawable.cue_logo_med_white),
        contentDescription = "Cue by thursday",
        modifier = modifier.aspectRatio(MediumLogoAspectRatio),
        contentScale = ContentScale.Fit
    )
}
