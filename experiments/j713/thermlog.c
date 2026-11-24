// J713 thermal logger, read only: HID temperature sensors and SMC keys.
//   thermlog list                                  every HID temperature sensor, every SMC 'flt ' key starting T or P
//   thermlog log OUT.csv PERIOD_MS SECONDS KEY...  all HID temperature sensors and the given SMC keys, every PERIOD_MS
// Build: clang -O2 -o thermlog thermlog.c -framework IOKit -framework CoreFoundation
#include <CoreFoundation/CoreFoundation.h>
#include <IOKit/IOKitLib.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

// ---- HID temperature sensors (private API, read only) ----
typedef struct __IOHIDEvent *IOHIDEventRef;
typedef struct __IOHIDServiceClient *IOHIDServiceClientRef;
typedef struct __IOHIDEventSystemClient *IOHIDEventSystemClientRef;
IOHIDEventSystemClientRef IOHIDEventSystemClientCreate(CFAllocatorRef);
int IOHIDEventSystemClientSetMatching(IOHIDEventSystemClientRef, CFDictionaryRef);
CFArrayRef IOHIDEventSystemClientCopyServices(IOHIDEventSystemClientRef);
IOHIDEventRef IOHIDServiceClientCopyEvent(IOHIDServiceClientRef, int64_t, int32_t, int64_t);
CFTypeRef IOHIDServiceClientCopyProperty(IOHIDServiceClientRef, CFStringRef);
double IOHIDEventGetFloatValue(IOHIDEventRef, int32_t);
#define HID_TEMP 15

static CFArrayRef hid_services(void) {
    IOHIDEventSystemClientRef c = IOHIDEventSystemClientCreate(kCFAllocatorDefault);
    int page = 0xff00, usage = 5;
    CFNumberRef p = CFNumberCreate(NULL, kCFNumberIntType, &page), u = CFNumberCreate(NULL, kCFNumberIntType, &usage);
    const void *k[] = {CFSTR("PrimaryUsagePage"), CFSTR("PrimaryUsage")}, *v[] = {p, u};
    CFDictionaryRef m = CFDictionaryCreate(NULL, k, v, 2, &kCFTypeDictionaryKeyCallBacks, &kCFTypeDictionaryValueCallBacks);
    IOHIDEventSystemClientSetMatching(c, m);
    return IOHIDEventSystemClientCopyServices(c);
}

static void hid_name(IOHIDServiceClientRef s, char *buf, size_t n) {
    CFTypeRef name = IOHIDServiceClientCopyProperty(s, CFSTR("Product"));
    if (!name || !CFStringGetCString(name, buf, n, kCFStringEncodingUTF8)) snprintf(buf, n, "?");
    if (name) CFRelease(name);
}

static double hid_temp(IOHIDServiceClientRef s) {
    IOHIDEventRef e = IOHIDServiceClientCopyEvent(s, HID_TEMP, 0, 0);
    if (!e) return NAN;
    double t = IOHIDEventGetFloatValue(e, HID_TEMP << 16);
    CFRelease(e);
    return t;
}

// ---- SMC (AppleSMC user client, read only) ----
typedef struct { char major, minor, build, reserved[1]; UInt16 release; } SMCVers;
typedef struct { UInt16 version, length; UInt32 cpuPLimit, gpuPLimit, memPLimit; } SMCPLimit;
typedef struct { UInt32 dataSize, dataType; char dataAttributes; } SMCKeyInfo;
typedef struct {
    UInt32 key; SMCVers vers; SMCPLimit pLimitData; SMCKeyInfo keyInfo;
    char result, status, data8; UInt32 data32; unsigned char bytes[32];
} SMCKeyData;
static io_connect_t smc;

static UInt32 k4(const char *s) { return ((UInt32)s[0] << 24) | ((UInt32)s[1] << 16) | ((UInt32)s[2] << 8) | (UInt32)s[3]; }
static void s4(UInt32 k, char *s) { s[0] = k >> 24; s[1] = k >> 16; s[2] = k >> 8; s[3] = k; s[4] = 0; }

static int smc_call(SMCKeyData *in, SMCKeyData *out) {
    size_t n = sizeof(SMCKeyData);
    return IOConnectCallStructMethod(smc, 2, in, sizeof(SMCKeyData), out, &n) == kIOReturnSuccess && out->result == 0;
}

static int smc_open(void) {
    io_service_t s = IOServiceGetMatchingService(kIOMainPortDefault, IOServiceMatching("AppleSMC"));
    return s && IOServiceOpen(s, mach_task_self(), 0, &smc) == kIOReturnSuccess;
}

// value of a key as double (flt, ui8/16/32, sp78), NAN if unreadable; type in t (5 chars)
static double smc_read(UInt32 key, char *t) {
    SMCKeyData in = {0}, out = {0};
    in.key = key; in.data8 = 9;                                   // key info
    if (!smc_call(&in, &out)) return NAN;
    UInt32 size = out.keyInfo.dataSize, type = out.keyInfo.dataType;
    if (t) s4(type, t);
    memset(&in, 0, sizeof in); in.key = key; in.keyInfo.dataSize = size; in.data8 = 5;   // read bytes
    memset(&out, 0, sizeof out);
    if (!smc_call(&in, &out)) return NAN;
    unsigned char *b = out.bytes;
    if (type == k4("flt ") && size == 4) { float f; memcpy(&f, b, 4); return f; }
    if (type == k4("ui8 ")) return b[0];
    if (type == k4("ui16")) return (b[0] << 8) | b[1];
    if (type == k4("ui32")) return ((UInt32)b[0] << 24) | ((UInt32)b[1] << 16) | ((UInt32)b[2] << 8) | b[3];
    if (type == k4("sp78")) return (int16_t)((b[0] << 8) | b[1]) / 256.0;
    return NAN;
}

static UInt32 smc_key_at(UInt32 i) {
    SMCKeyData in = {0}, out = {0};
    in.data8 = 8; in.data32 = i;
    return smc_call(&in, &out) ? out.key : 0;
}

static double now(clockid_t c) { struct timespec ts; clock_gettime(c, &ts); return ts.tv_sec + ts.tv_nsec * 1e-9; }

int main(int argc, char **argv) {
    if (argc < 2) { fprintf(stderr, "usage: thermlog list | log OUT.csv PERIOD_MS SECONDS KEY...\n"); return 2; }
    if (!smc_open()) { fprintf(stderr, "AppleSMC: cannot open\n"); return 1; }
    CFArrayRef sv = hid_services();
    CFIndex ns = sv ? CFArrayGetCount(sv) : 0;
    char name[128], ks[5], ty[5];
    if (!strcmp(argv[1], "list")) {
        for (CFIndex i = 0; i < ns; i++) {
            IOHIDServiceClientRef s = (IOHIDServiceClientRef)CFArrayGetValueAtIndex(sv, i);
            hid_name(s, name, sizeof name);
            printf("hid\t%s\t%.3f\n", name, hid_temp(s));
        }
        UInt32 n = (UInt32)smc_read(k4("#KEY"), NULL);
        printf("smc keys\t%u\n", n);
        for (UInt32 i = 0; i < n; i++) {
            UInt32 k = smc_key_at(i);
            s4(k, ks);
            if (ks[0] != 'T' && ks[0] != 'P') continue;
            double v = smc_read(k, ty);
            if (!strcmp(ty, "flt ")) printf("smc\t%s\t%s\t%.4f\n", ks, ty, v);
        }
        return 0;
    }
    if (!strcmp(argv[1], "log") && argc >= 5) {
        FILE *f = fopen(argv[2], "w");
        double period = atof(argv[3]) / 1000.0, secs = atof(argv[4]);
        int nk = argc - 5;
        static char allkeys[4096][5];
        char **keys = argv + 5;
        static char *kp[4096];
        if (nk == 1 && !strcmp(argv[5], "ALL")) {                 // every 'flt ' key starting T or P
            UInt32 n = (UInt32)smc_read(k4("#KEY"), NULL);
            nk = 0;
            for (UInt32 i = 0; i < n && nk < 4096; i++) {
                UInt32 k = smc_key_at(i);
                s4(k, allkeys[nk]);
                if (allkeys[nk][0] != 'T' && allkeys[nk][0] != 'P') continue;
                smc_read(k, ty);
                if (!strcmp(ty, "flt ")) { kp[nk] = allkeys[nk]; nk++; }
            }
            keys = kp;
        }
        fprintf(f, "t_mono,t_unix");
        for (CFIndex i = 0; i < ns; i++) {
            hid_name((IOHIDServiceClientRef)CFArrayGetValueAtIndex(sv, i), name, sizeof name);
            for (char *c = name; *c; c++) if (*c == ',') *c = ';';
            fprintf(f, ",hid%ld:%s", (long)i, name);
        }
        for (int j = 0; j < nk; j++) fprintf(f, ",smc:%s", keys[j]);
        fprintf(f, "\n");
        double t0 = now(CLOCK_MONOTONIC);
        for (long step = 0;; step++) {
            double target = t0 + step * period;
            double d = target - now(CLOCK_MONOTONIC);
            if (d > 0) usleep((useconds_t)(d * 1e6));
            if (now(CLOCK_MONOTONIC) - t0 > secs) break;
            fprintf(f, "%.3f,%.3f", now(CLOCK_MONOTONIC) - t0, now(CLOCK_REALTIME));
            for (CFIndex i = 0; i < ns; i++)
                fprintf(f, ",%.3f", hid_temp((IOHIDServiceClientRef)CFArrayGetValueAtIndex(sv, i)));
            for (int j = 0; j < nk; j++) fprintf(f, ",%.4f", smc_read(k4(keys[j]), NULL));
            fprintf(f, "\n");
            fflush(f);
        }
        fclose(f);
        return 0;
    }
    fprintf(stderr, "bad arguments\n");
    return 2;
}
