/* espeak-ng synthesis -> linear resample to 48 kHz -> libopus encode.
 * Single WASM module for the rndimg speech worker. */
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <espeak-ng/espeak_ng.h>
#include <espeak-ng/speak_lib.h>
#include <opus.h>

#define OUT_RATE 48000
#define FRAME_SIZE 1920

static uint8_t *pcm = NULL;
static size_t pcm_len = 0, pcm_cap = 0;
static int16_t *pcm48 = NULL;
static size_t pcm48_cap = 0;
static uint8_t *pkts = NULL;
static size_t pkts_len = 0, pkts_cap = 0;
static int32_t *sizes = NULL;
static size_t sizes_len = 0, sizes_cap = 0;

static OpusEncoder *enc = NULL;
static int espeak_rate = 0;

static void *grow(void *p, size_t *cap, size_t need, size_t elem)
{
	if (need <= *cap)
		return p;
	size_t c = *cap ? *cap : 8192;
	while (c < need)
		c *= 2;
	p = realloc(p, c * elem);
	*cap = c;
	return p;
}

static int on_audio(short *wav, int numsamples, espeak_EVENT *events)
{
	(void)events;
	if (wav != NULL && numsamples > 0) {
		pcm = (uint8_t *)grow(pcm, &pcm_cap, pcm_len + (size_t)numsamples * 2, 1);
		memcpy(pcm + pcm_len, wav, (size_t)numsamples * 2);
		pcm_len += (size_t)numsamples * 2;
	}
	return 0;
}


#include <errno.h>
#include <sys/stat.h>
int sp_probe(const char *path)
{
	struct stat st;
	if (stat(path, &st) != 0)
		return -errno;
	if (S_ISDIR(st.st_mode))
		return -2;
	return (int)st.st_size;
}

int sp_init(void)
{
	int sr = espeak_Initialize(AUDIO_OUTPUT_SYNCHRONOUS, 0, "/espeak-ng-data", espeakINITIALIZE_DONT_EXIT);
	if (sr < 8000)
		return -1;
	espeak_rate = sr;
	espeak_SetSynthCallback(on_audio);

	int err = 0;
	enc = opus_encoder_create(OUT_RATE, 1, OPUS_APPLICATION_VOIP, &err);
	if (err != OPUS_OK || enc == NULL)
		return -2;
	opus_encoder_ctl(enc, OPUS_SET_BITRATE(24000));
	opus_encoder_ctl(enc, OPUS_SET_COMPLEXITY(2));
	opus_encoder_ctl(enc, OPUS_SET_SIGNAL(OPUS_SIGNAL_VOICE));
	return sr;
}

int sp_set_voice(const char *voice)
{
	return espeak_ng_SetVoiceByName(voice) == ENS_OK ? 0 : -1;
}

int sp_rate(void)
{
	return espeak_rate;
}

int sp_synth(const char *text)
{
	pcm_len = 0;
	pkts_len = 0;
	sizes_len = 0;
	espeak_ng_SetRandSeed(1);

	if (espeak_Synth(text, strlen(text) + 1, 0, POS_CHARACTER, 0,
	                 espeakCHARS_UTF8, NULL, NULL) != EE_OK)
		return -1;

	size_t n = pcm_len / 2;
	if (n == 0)
		return 0;

	size_t out_n = (size_t)(((uint64_t)n * OUT_RATE) / (uint64_t)espeak_rate);
	pcm48 = (int16_t *)grow(pcm48, &pcm48_cap, out_n + 1, sizeof(int16_t));
	const int16_t *in = (const int16_t *)pcm;
	for (size_t j = 0; j < out_n; j++) {
		uint64_t numer = (uint64_t)j * (uint64_t)espeak_rate;
		size_t i = (size_t)(numer / OUT_RATE);
		uint32_t frac = (uint32_t)((numer % OUT_RATE) * 65536 / OUT_RATE);
		int32_t a = in[i];
		int32_t b = (i + 1 < n) ? in[i + 1] : a;
		pcm48[j] = (int16_t)(a + (int32_t)(((int64_t)(b - a) * (int64_t)frac) >> 16));
	}

	uint8_t packet[1275];
	size_t frames = (out_n + FRAME_SIZE - 1) / FRAME_SIZE;
	for (size_t f = 0; f < frames; f++) {
		int16_t frame[FRAME_SIZE] = {0};
		size_t off = f * FRAME_SIZE;
		size_t cnt = out_n - off < FRAME_SIZE ? out_n - off : FRAME_SIZE;
		memcpy(frame, pcm48 + off, cnt * sizeof(int16_t));
		int len = opus_encode(enc, frame, FRAME_SIZE, packet, sizeof(packet));
		if (len < 0)
			return -2;
		pkts = (uint8_t *)grow(pkts, &pkts_cap, pkts_len + (size_t)len, 1);
		memcpy(pkts + pkts_len, packet, (size_t)len);
		pkts_len += (size_t)len;
		sizes = (int32_t *)grow(sizes, &sizes_cap, sizes_len + 1, sizeof(int32_t));
		sizes[sizes_len++] = len;
	}
	opus_encoder_ctl(enc, OPUS_RESET_STATE);
	return (int)sizes_len;
}

int sp_packet_count(void)
{
	return (int)sizes_len;
}

int sp_packet_bytes(void)
{
	return (int)pkts_len;
}

uint8_t *sp_packet_data(void)
{
	return pkts;
}

int32_t *sp_packet_sizes(void)
{
	return sizes;
}
