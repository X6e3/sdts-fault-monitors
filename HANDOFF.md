# SDTS araştırma devri — 17 Kasım 2026

## Depo ve çalışma ortamı

- **OBSERVED.** Arch ana checkout’u `/home/x6e3/Research/dmreda-sdts-research-main`. `protocol/thermal-single-sensor-v1` HEAD’i `c21f152cf49c48feb90c6c60bbb3636ebe9cbd43`. GitHub izleme dalından dört commit ileride. Protokol dosyası v2’yi içeriyor.
- **OBSERVED.** İzolasyon commit’i `c04305ab36466852c7963d8cee7ddfcc8e36d22f`. Oracle CAL bu commit’in temiz Arch kopyasında çalıştı. Commit gerçek Arch deposunda `codex/thermal-highs-isolation` dalına yerel Git bundle ile alındı. Bu dal için ayrı worktree `work/sdts-arch`.
- **OBSERVED.** Orijinal `results/thermal_oracle_cal_v1.out` 3.052 bayt. SHA-256 `c6312a3135daeae34cf568e5b93e3407d849fd0441e56c2339d5a77099d086c9`. Bu geçmiş koşu sertifika hatasıyla `1` çıkış kodunda sonlanmış. Taşınan `._*` dosyaları macOS metadata’sı.
- **OBSERVED.** İlk incelemede Mac `Mac16,12`, Apple M4 ve aynı HEAD’deydi. `x6e3@192.168.1.100` bağlantısı kayıtlı host anahtarıyla doğrulandı. İlk bakışta iki CPU kullanan süreç dahil dokuz Python süreç kaydı vardı. Hepsi kendi halinde bırakıldı. Kullanıcı Arch kopyasına geçtikten sonra erişim ve geliştirme Arch’ta yürütüldü.
- **OBSERVED.** Arch ortamı `work/arch-venv` içinde CPython 3.12.13, NumPy 2.5.5, SciPy 1.18.1, paket içi HiGHS 1.12.0. Mac doğrulamasında da bu sürümler görüldü. CAL için 12 işçi, BLAS/OMP başına bir iş parçacığı ve her solver alt sürecine 120 saniye kullanıldı. GPU kullanılmadı.

## 410197/E0 ve izolasyon

- **OBSERVED.** Mac doğrulamasında presolve kapalı `highs-ipm`, PID 37506, `SIGSEGV` (`−11`) ile çıktı. Solver status dönmedi. Presolve kapalı `highs-ds` aynı diziyi `0` çıkış kodu ve SciPy status `0` ile çözdü. Tutarlı, `0.2983090534559669 ≤ δ* ≤ 0.2983090922446756` °C. Arch’ta iki yöntem de ayrı denemelerde tamamlandı. Arch CAL sağlıklı satırı kararın nihai Arch kanıtıdır.
- **OBSERVED.** Mac crash raporu `python3.12-2026-11-17-073110.ips`, aynı PID için `HEkkDualRHS::chooseNormal` özyinelemesini ve `solveLpSimplex` çağrısını gösterdi. Daha önceki altı Mac Python crash raporu da aynı yığını ve macOS yığın taşması teşhisini taşıyordu. HiGHS v1.12.0’da `chooseNormal` aday listesini yeniden kurduğunda kendini çağırıyor. [HiGHS v1.12.0 kaynak kodu](https://github.com/ERGO-Code/HiGHS/blob/v1.12.0/highs/simplex/HEkkDualRHS.cpp)
- **DERIVED.** IPM seçili olmasına rağmen bu hata HiGHS’in dual-simplex çözüm aşamasında oluştu. HiGHS IPX `Unknown` veya bazı `UnboundedOrInfeasible` durumlarında simplex ile toparlamaya dönebiliyor. Bu özel girişte IPX’in dönüştüğü iç durum ve Arch–Mac farkının hangi sayısal adımdan kaynaklandığı **UNKNOWN**. [HiGHS v1.12.0 `solveLp`](https://github.com/ERGO-Code/HiGHS/blob/v1.12.0/highs/lp_data/HighsSolve.cpp#L131-L168)
- **OBSERVED.** `thermal_oracle.py` her çağrı için yeni Python alt süreci başlatıyor. Yöntem, presolve, örnek sayısı, PID, süre, OS çıkış kodu, sinyal ve solver durumu ilgili `attempt.json` içinde. `stdout.txt` ve `stderr.txt` ayrı. Bir çökme veya zaman aşımı sonraki yönteme geçiyor. Sertifika yetmezse karar `undetermined` (`UNKNOWN`).
- **DERIVED.** Üst sınır uygulanabilir ortam yolundan gelir. Alt sınır için dual işaretler projekte edilir ve durağanlık kalıntısının olası etkisi `|r|ᵀ caps` olarak çıkarılır. P6’da dış offset sınırı dahil oluşu, iç uygulanabilir tanık taşmayı kanıtlar. Sınırlar ve yuvarlama tamponları LP’nin sabit kayan nokta katsayılarıyla hesaplanır.
- **OBSERVED.** Yedi üreteç testi hem Arch hem Mac’te geçti. Dört oracle testi de iki platformda geçti. Bunlar alt süreç sinyali ve fallback, çözücü kanıtı yokken `UNKNOWN`, bilinen offset aralığı, büyük sıçrama için dual sınır.

## Tekrarlama

Bağımsız ortam için `uv venv --python 3.12.13` ve `uv pip install` ile `numpy==2.5.5` ve `scipy==1.18.1` kullan. Oracle koşusunda temiz kaynak commit’i ve yeni çıktı dizini kullan.

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 SDTS_CAL_WORKERS=12 SDTS_HIGHS_TIMEOUT=120 \
  "$PYTHON" -B -u experiments/oracle/validate_cal.py "$CAL_OUT"
```

## İlk koşu ve iki takip düzeltmesi

- **OBSERVED.** İlk tam doğrulama `c04305a` ile 2.027,9 saniyede tamamlandı. 9.719 solver denemesinin 333’ü SciPy durum `4` döndürdü. `410028/noise_x4/E0` ve `410029/jump_5/E0` için iki yöntem de durum 4 verdi. İkisi ilk haritada `UNKNOWN` kaldı. E1 kararları `inconsistent` olduğu için P2’de ilk koşu 748/750 sertifikalı eşleşme verdi.
- **DERIVED.** Hız kısıtı açıkken `2d ≥ |z[k] − z[k−1]| − ρ_A` eşitsizliği her açıklayıcı yol için geçerli. `4e87cd3` bu sınırı iki yöntemden sonra karar açık kalırsa değerlendiriyor. `410028/noise_x4/E0` için tanık örneği 3233 ve sınır 1,1715988170 °C. `410029/jump_5/E0` için tanık örneği 563 ve sınır 2,4371547329 °C. İkisi de δ=0,3 °C sınırının üstünde. Bu alt sınırlar karar vermeye yeterli, δ*’ın daha sıkı değeri açık.
- **OBSERVED.** İlk gecikme taramasında `410001/drift_0.001` iki kolda `t*=2965` tahminiyle `UNKNOWN` olarak etiketlendi. Hedefli yeniden incelemede her iki kolda uzunluğu 2965 olan önek tutarlı (`d_up≈0,2972090`), uzunluğu 2966 olan önek tutarsız (`d_lo≈0,3242868`). `17db9aa` kesinliği, aramadaki tüm ara problar yerine bu son komşu önek çiftinden belirliyor. E0’da 2967 uzunluklu önek için durum `UNKNOWN` olarak kayıtlarda kaldı.

## Oracle CAL sonuçları

**OBSERVED.** `validate_cal.py` tamamlandı. Süre 2358.9 sn. Aşağıdaki aralıklarda iki uç da dahil. Tohum bazındaki δ alt ve üst sınırları, offset tanıkları ve solver denemeleri kanıt paketinde yer alıyor.

### P1 ve V0

| İkiz | Çift | CAL tohumları | En büyük |Δy| | Aynı sertifikalı LP kararı | Doğrudan LP tohumları |
| --- | --- | --- | --- | --- | --- |
| offset_open | 1200 | 410000–410199 | 7.11e-14 | 12/12 | 410000, 410197 |
| offset_closed | 600 | 410000–410199 | 2.84e-14 | 6/6 | 410000, 410197 |
| stuck_rest | 200 | 410000–410199 | 0 | 2/2 | 410000, 410197 |


**OBSERVED.** V0 için en büyük sonlu primal üst sınır 0.2993984491 °C.

| Kol | Karar | Adet | Tohumlar |
| --- | --- | --- | --- |
| E0 | consistent | 200 | 410000–410199 |
| E1 | consistent | 200 | 410000–410199 |

### P2, P4, P5, P6 ve P7

P2 için en büyük |z(E0) − z(E1)| 1.14e-13 °C.

| P2 hücresi | Sertifikalı eşleşme | Eşleşen tohumlar | Farklı tohumlar | UNKNOWN içeren tohumlar |
| --- | --- | --- | --- | --- |
| offset_1 | 50 | 410000–410049 | — | — |
| offset_3 | 50 | 410000–410049 | — | — |
| jump_0.2 | 50 | 410000–410049 | — | — |
| jump_0.5 | 50 | 410000–410049 | — | — |
| jump_1 | 50 | 410000–410049 | — | — |
| jump_2 | 50 | 410000–410049 | — | — |
| jump_5 | 50 | 410000–410049 | — | — |
| drift_0.0005 | 50 | 410000–410049 | — | — |
| drift_0.001 | 50 | 410000–410049 | — | — |
| drift_0.002 | 50 | 410000–410049 | — | — |
| drift_0.005 | 50 | 410000–410049 | — | — |
| drift_0.02 | 50 | 410000–410049 | — | — |
| drift_0.1 | 50 | 410000–410049 | — | — |
| noise_x2 | 50 | 410000–410049 | — | — |
| noise_x4 | 50 | 410000–410049 | — | — |

| P4 hücresi / kol | Önce / başlangıçta | Adet | Tohumlar |
| --- | --- | --- | --- |
| jump_2/E0 | consistent / inconsistent | 200 | 410000–410199 |
| jump_2/E1 | consistent / inconsistent | 200 | 410000–410199 |
| jump_5/E0 | consistent / inconsistent | 200 | 410000–410199 |
| jump_5/E1 | consistent / inconsistent | 200 | 410000–410199 |

| P5 hücresi / kol | Kutusuz / kutulu | Adet | Tohumlar |
| --- | --- | --- | --- |
| offset_1/E0 | consistent / consistent | 40 | 410000–410003, 410005, 410008, 410011–410022, 410024, 410026–410033, 410035–410044, 410046, 410048–410049 |
| offset_1/E0 | consistent / inconsistent | 10 | 410004, 410006–410007, 410009–410010, 410023, 410025, 410034, 410045, 410047 |
| offset_1/E1 | consistent / consistent | 40 | 410000–410003, 410005, 410008, 410011–410022, 410024, 410026–410033, 410035–410044, 410046, 410048–410049 |
| offset_1/E1 | consistent / inconsistent | 10 | 410004, 410006–410007, 410009–410010, 410023, 410025, 410034, 410045, 410047 |
| offset_3/E0 | consistent / consistent | 15 | 410000, 410002, 410005, 410008, 410012–410013, 410018, 410020–410022, 410024, 410033, 410040, 410042, 410049 |
| offset_3/E0 | consistent / inconsistent | 35 | 410001, 410003–410004, 410006–410007, 410009–410011, 410014–410017, 410019, 410023, 410025–410032, 410034–410039, 410041, 410043–410048 |
| offset_3/E1 | consistent / consistent | 15 | 410000, 410002, 410005, 410008, 410012–410013, 410018, 410020–410022, 410024, 410033, 410040, 410042, 410049 |
| offset_3/E1 | consistent / inconsistent | 35 | 410001, 410003–410004, 410006–410007, 410009–410011, 410014–410017, 410019, 410023, 410025–410032, 410034–410039, 410041, 410043–410048 |

P6 için R=1 °C. Uyum 400/400. UNKNOWN 0. Sınır bandı 0.

| Kol | Öngörü bölgesi | Oracle | Adet | Tohumlar |
| --- | --- | --- | --- | --- |
| E0 | sertifikalanamaz | not_certifiable | 200 | 410000–410199 |
| E1 | sertifikalanamaz | not_certifiable | 200 | 410000–410199 |

P6 için R=3 °C. Uyum 268/268. UNKNOWN 0. Sınır bandı 132.

| Kol | Öngörü bölgesi | Oracle | Adet | Tohumlar |
| --- | --- | --- | --- | --- |
| E0 | sertifikalanamaz | not_certifiable | 63 | 410000, 410002, 410004, 410007, 410009–410010, 410012–410013, 410018, 410020, 410022, 410042, 410047, 410050–410051, 410053, 410055–410057, 410060–410061, 410070–410071, 410073, 410075, 410083, 410085–410086, 410089–410090, 410092–410095, 410100–410102, 410105–410106, 410111, 410113, 410115, 410122–410123, 410126–410127, 410137, 410141–410143, 410145, 410147–410150, 410152, 410157, 410170, 410174, 410176, 410179–410180, 410194 |
| E0 | sınır bandı | certifiable | 26 | 410003, 410011, 410019, 410026, 410035, 410037, 410046, 410063, 410074, 410077, 410081, 410107, 410114, 410129–410130, 410136, 410156, 410159–410161, 410167, 410175, 410182, 410185, 410188, 410190 |
| E0 | sınır bandı | not_certifiable | 39 | 410005–410006, 410008, 410021, 410023–410025, 410033–410034, 410040, 410045, 410049, 410058, 410064–410065, 410067–410068, 410072, 410079, 410084, 410098, 410109, 410112, 410116–410117, 410119, 410124, 410128, 410135, 410139, 410163, 410165–410166, 410169, 410177, 410181, 410184, 410196, 410199 |
| E0 | sınır bandı | undetermined | 1 | 410172 |
| E0 | sertifikalanabilir | certifiable | 71 | 410001, 410014–410017, 410027–410032, 410036, 410038–410039, 410041, 410043–410044, 410048, 410052, 410054, 410059, 410062, 410066, 410069, 410076, 410078, 410080, 410082, 410087–410088, 410091, 410096–410097, 410099, 410103–410104, 410108, 410110, 410118, 410120–410121, 410125, 410131–410134, 410138, 410140, 410144, 410146, 410151, 410153–410155, 410158, 410162, 410164, 410168, 410171, 410173, 410178, 410183, 410186–410187, 410189, 410191–410193, 410195, 410197–410198 |
| E1 | sertifikalanamaz | not_certifiable | 63 | 410000, 410002, 410004, 410007, 410009–410010, 410012–410013, 410018, 410020, 410022, 410042, 410047, 410050–410051, 410053, 410055–410057, 410060–410061, 410070–410071, 410073, 410075, 410083, 410085–410086, 410089–410090, 410092–410095, 410100–410102, 410105–410106, 410111, 410113, 410115, 410122–410123, 410126–410127, 410137, 410141–410143, 410145, 410147–410150, 410152, 410157, 410170, 410174, 410176, 410179–410180, 410194 |
| E1 | sınır bandı | certifiable | 26 | 410003, 410011, 410019, 410026, 410035, 410037, 410046, 410063, 410074, 410077, 410081, 410107, 410114, 410129–410130, 410136, 410156, 410159–410161, 410167, 410175, 410182, 410185, 410188, 410190 |
| E1 | sınır bandı | not_certifiable | 39 | 410005–410006, 410008, 410021, 410023–410025, 410033–410034, 410040, 410045, 410049, 410058, 410064–410065, 410067–410068, 410072, 410079, 410084, 410098, 410109, 410112, 410116–410117, 410119, 410124, 410128, 410135, 410139, 410163, 410165–410166, 410169, 410177, 410181, 410184, 410196, 410199 |
| E1 | sınır bandı | undetermined | 1 | 410172 |
| E1 | sertifikalanabilir | certifiable | 71 | 410001, 410014–410017, 410027–410032, 410036, 410038–410039, 410041, 410043–410044, 410048, 410052, 410054, 410059, 410062, 410066, 410069, 410076, 410078, 410080, 410082, 410087–410088, 410091, 410096–410097, 410099, 410103–410104, 410108, 410110, 410118, 410120–410121, 410125, 410131–410134, 410138, 410140, 410144, 410146, 410151, 410153–410155, 410158, 410162, 410164, 410168, 410171, 410173, 410178, 410183, 410186–410187, 410189, 410191–410193, 410195, 410197–410198 |

**OBSERVED.** P7’de E1 için 50/50 koşu en geç k+30’da tutarsız. 40 koşu k’dan önce tutarsız, 10/50 koşuda ilk tutarsızlık [k,k+30] içinde. Burada k, arıza başlangıcından sonraki ilk ≥5 W komut değişimi. %95 eşiği son tarih yorumunda sağlandı, yalnız [k,k+30] penceresi yorumunda sağlanmadı.

| Kol | Karar veya k-1 / k+30 | Adet | Tohumlar |
| --- | --- | --- | --- |
| E0 | consistent | 50 | 410000–410049 |
| E1 | consistent / inconsistent | 10 | 410009, 410011, 410014, 410019, 410034, 410036, 410041–410042, 410044, 410048 |
| E1 | inconsistent / inconsistent | 40 | 410000–410008, 410010, 410012–410013, 410015–410018, 410020–410033, 410035, 410037–410040, 410043, 410045–410047, 410049 |

### 38 hücrede tam koşu kararları

| Hücre / kol | Tutarlı | Tutarsız | UNKNOWN |
| --- | --- | --- | --- |
| healthy/E0 | 50 · 410000–410049 | 0 · — | 0 · — |
| healthy/E1 | 50 · 410000–410049 | 0 · — | 0 · — |
| offset_1/E0 | 40 · 410000–410003, 410005, 410008, 410011–410022, 410024, 410026–410033, 410035–410044, 410046, 410048–410049 | 10 · 410004, 410006–410007, 410009–410010, 410023, 410025, 410034, 410045, 410047 | 0 · — |
| offset_1/E1 | 40 · 410000–410003, 410005, 410008, 410011–410022, 410024, 410026–410033, 410035–410044, 410046, 410048–410049 | 10 · 410004, 410006–410007, 410009–410010, 410023, 410025, 410034, 410045, 410047 | 0 · — |
| offset_3/E0 | 15 · 410000, 410002, 410005, 410008, 410012–410013, 410018, 410020–410022, 410024, 410033, 410040, 410042, 410049 | 35 · 410001, 410003–410004, 410006–410007, 410009–410011, 410014–410017, 410019, 410023, 410025–410032, 410034–410039, 410041, 410043–410048 | 0 · — |
| offset_3/E1 | 15 · 410000, 410002, 410005, 410008, 410012–410013, 410018, 410020–410022, 410024, 410033, 410040, 410042, 410049 | 35 · 410001, 410003–410004, 410006–410007, 410009–410011, 410014–410017, 410019, 410023, 410025–410032, 410034–410039, 410041, 410043–410048 | 0 · — |
| jump_0.2/E0 | 0 · — | 50 · 410000–410049 | 0 · — |
| jump_0.2/E1 | 0 · — | 50 · 410000–410049 | 0 · — |
| jump_0.5/E0 | 0 · — | 50 · 410000–410049 | 0 · — |
| jump_0.5/E1 | 0 · — | 50 · 410000–410049 | 0 · — |
| jump_1/E0 | 0 · — | 50 · 410000–410049 | 0 · — |
| jump_1/E1 | 0 · — | 50 · 410000–410049 | 0 · — |
| jump_2/E0 | 0 · — | 50 · 410000–410049 | 0 · — |
| jump_2/E1 | 0 · — | 50 · 410000–410049 | 0 · — |
| jump_5/E0 | 0 · — | 50 · 410000–410049 | 0 · — |
| jump_5/E1 | 0 · — | 50 · 410000–410049 | 0 · — |
| drift_0.0005/E0 | 34 · 410000–410003, 410005, 410008, 410012–410022, 410024, 410027–410031, 410033, 410036–410038, 410040–410044, 410046, 410049 | 16 · 410004, 410006–410007, 410009–410011, 410023, 410025–410026, 410032, 410034–410035, 410039, 410045, 410047–410048 | 0 · — |
| drift_0.0005/E1 | 34 · 410000–410003, 410005, 410008, 410012–410022, 410024, 410027–410031, 410033, 410036–410038, 410040–410044, 410046, 410049 | 16 · 410004, 410006–410007, 410009–410011, 410023, 410025–410026, 410032, 410034–410035, 410039, 410045, 410047–410048 | 0 · — |
| drift_0.001/E0 | 14 · 410000, 410002, 410005, 410008, 410012–410013, 410018, 410020, 410022, 410024, 410033, 410040, 410042, 410049 | 36 · 410001, 410003–410004, 410006–410007, 410009–410011, 410014–410017, 410019, 410021, 410023, 410025–410032, 410034–410039, 410041, 410043–410048 | 0 · — |
| drift_0.001/E1 | 14 · 410000, 410002, 410005, 410008, 410012–410013, 410018, 410020, 410022, 410024, 410033, 410040, 410042, 410049 | 36 · 410001, 410003–410004, 410006–410007, 410009–410011, 410014–410017, 410019, 410021, 410023, 410025–410032, 410034–410039, 410041, 410043–410048 | 0 · — |
| drift_0.002/E0 | 0 · — | 50 · 410000–410049 | 0 · — |
| drift_0.002/E1 | 0 · — | 50 · 410000–410049 | 0 · — |
| drift_0.005/E0 | 0 · — | 50 · 410000–410049 | 0 · — |
| drift_0.005/E1 | 0 · — | 50 · 410000–410049 | 0 · — |
| drift_0.02/E0 | 0 · — | 50 · 410000–410049 | 0 · — |
| drift_0.02/E1 | 0 · — | 50 · 410000–410049 | 0 · — |
| drift_0.1/E0 | 0 · — | 50 · 410000–410049 | 0 · — |
| drift_0.1/E1 | 0 · — | 50 · 410000–410049 | 0 · — |
| noise_x2/E0 | 0 · — | 50 · 410000–410049 | 0 · — |
| noise_x2/E1 | 0 · — | 50 · 410000–410049 | 0 · — |
| noise_x4/E0 | 0 · — | 50 · 410000–410049 | 0 · — |
| noise_x4/E1 | 0 · — | 50 · 410000–410049 | 0 · — |
| stuck/E0 | 50 · 410000–410049 | 0 · — | 0 · — |
| stuck/E1 | 0 · — | 50 · 410000–410049 | 0 · — |
| gain_0.01/E0 | 0 · — | 50 · 410000–410049 | 0 · — |
| gain_0.01/E1 | 0 · — | 50 · 410000–410049 | 0 · — |
| gain_0.05/E0 | 0 · — | 50 · 410000–410049 | 0 · — |
| gain_0.05/E1 | 0 · — | 50 · 410000–410049 | 0 · — |

### Tohum bazında gecikme

Gecikme taraması `17db9aa` ile tekrarlandı.

Her liste 410000–410009 sırasındadır. Değerler t* − t_f (s). `—` tüm koşuda tutarlı, `~` sertifikasız kestirim.

| Hücre / kol | Gecikmeler, tohum sırasıyla |
| --- | --- |
| healthy/E0 | —, —, —, —, —, —, —, —, —, — |
| healthy/E1 | —, —, —, —, —, —, —, —, —, — |
| offset_1/E0 | —, —, —, —, -529, —, -400, -308, —, -524 |
| offset_1/E1 | —, —, —, —, -529, —, -400, -308, —, -524 |
| offset_3/E0 | —, -357, —, -362, -529, —, -402, -308, —, -524 |
| offset_3/E1 | —, -357, —, -362, -529, —, -402, -308, —, -524 |
| jump_0.2/E0 | 7, 0, 3, 0, 0, 0, 3, 5, 0, 5 |
| jump_0.2/E1 | 7, 0, 3, 0, 0, 0, 3, 5, 0, 5 |
| jump_0.5/E0 | 0, 0, 0, 0, 0, 0, 0, 2, 0, 0 |
| jump_0.5/E1 | 0, 0, 0, 0, 0, 0, 0, 2, 0, 0 |
| jump_1/E0 | 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 |
| jump_1/E1 | 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 |
| jump_2/E0 | 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 |
| jump_2/E1 | 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 |
| jump_5/E0 | 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 |
| jump_5/E1 | 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 |
| drift_0.0005/E0 | —, —, —, —, 131, —, 1769, 865, —, 661 |
| drift_0.0005/E1 | —, —, —, —, 131, —, 1769, 865, —, 661 |
| drift_0.001/E0 | —, 2608, —, 2906, 76, —, 818, 430, —, 353 |
| drift_0.001/E1 | —, 2608, —, 2906, 76, —, 818, 430, —, 353 |
| drift_0.002/E0 | 70, 52, 18, 44, 30, 96, 28, 37, 94, 87 |
| drift_0.002/E1 | 70, 52, 18, 44, 30, 96, 28, 37, 94, 87 |
| drift_0.005/E0 | 14, 23, 18, 36, 20, 23, 28, 13, 17, 21 |
| drift_0.005/E1 | 14, 23, 18, 36, 20, 23, 28, 13, 17, 21 |
| drift_0.02/E0 | 7, 11, 13, 10, 9, 9, 11, 7, 7, 5 |
| drift_0.02/E1 | 7, 11, 13, 10, 9, 9, 11, 7, 7, 5 |
| drift_0.1/E0 | 4, 5, 3, 3, 3, 3, 3, 3, 2, 4 |
| drift_0.1/E1 | 4, 5, 3, 3, 3, 3, 3, 3, 2, 4 |
| noise_x2/E0 | 3, 0, 1, 0, 0, 0, 3, 0, 0, 5 |
| noise_x2/E1 | 3, 0, 1, 0, 0, 0, 3, 0, 0, 5 |
| noise_x4/E0 | 1, 0, 0, 0, 0, 0, 0, 0, 0, 0 |
| noise_x4/E1 | 1, 0, 0, 0, 0, 0, 0, 0, 0, 0 |
| stuck/E0 | —, —, —, —, —, —, —, —, —, — |
| stuck/E1 | 8, 1, 1, 4, 2, 1, 1, 8, 2, 5 |
| gain_0.01/E0 | 0, 0, 0, 0, 0, 0, 0, 2, 0, 0 |
| gain_0.01/E1 | 0, 0, 0, 0, 0, 0, 1, 2, 0, 0 |
| gain_0.05/E0 | 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 |
| gain_0.05/E1 | 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 |

### Çözücü denemeleri

| Yöntem | Alt süreç sonucu | SciPy solver durumu | Adet |
| --- | --- | --- | --- |
| highs-ds | returned | 0 | 9044 |
| highs-ds | returned | 4 | 326 |
| highs-ipm | returned | 0 | 342 |
| highs-ipm | returned | 4 | 7 |

Ayrıntılı 333 solver hatası kanıt paketindeki attempt.json kayıtlarında yer alıyor.

- P5/offset_1/410029-E0 · highs-ds · margin · 3600 örnek · durum 4
- V0_P6/healthy/410028-E0 · highs-ds · offset · 3600 örnek · durum 4
- cells/jump_1/410028-E0 · highs-ds · margin · 3600 örnek · durum 4
- cells/jump_1/410029-E0 · highs-ds · margin · 3600 örnek · durum 4
- cells/jump_5/410028-E0 · highs-ds · margin · 3600 örnek · durum 4
- cells/jump_5/410029-E0 · highs-ds · margin · 3600 örnek · durum 4
- cells/jump_5/410029-E0 · highs-ipm · margin · 3600 örnek · durum 4
- cells/noise_x2/410029-E0 · highs-ds · margin · 3600 örnek · durum 4
- cells/noise_x4/410028-E0 · highs-ds · margin · 3600 örnek · durum 4
- cells/noise_x4/410028-E0 · highs-ipm · margin · 3600 örnek · durum 4
- cells/noise_x4/410029-E0 · highs-ds · margin · 3600 örnek · durum 4
- cells/offset_1/410029-E0 · highs-ds · margin · 3600 örnek · durum 4

| Test / hücre / tohum-kol | Önek | Tanık örneği | Bağımsız alt sınır | Primal üst sınır |
| --- | --- | --- | --- | --- |
| cells/jump_5/410029-E0 | 3600 | 563 | 2.437154733 | 4.774231436 |
| cells/noise_x4/410028-E0 | 3600 | 3233 | 1.171598817 | 1.5103519 |

**DERIVED.** d* ölçüm dizisine göre sonsuzluk normunda 1-Lipschitz. CAL haritasındaki 1 ve 3 °C açık döngü offset çiftlerinin 200/200’ünde P1 kararını kayıtlı sınırlar ve ölçülen ikiz farkı ile taşıdık. Kalan açık ve kapalı döngü çiftlerinde üreteç ve makine kayıtları mevcut. Doğrudan oracle örneklemi yukarıdaki tabloda.

## Çevrimiçi makine

**OBSERVED.** `96cf74d` ile 38 hücrede 7.600 CAL koşusu. P1 2.000/2.000, P2 3.000/3.000, P4 800/800, kutusuz P5 200/200. Sağlıklı 400 koşuda TUTARSIZ yok. 192 sağlıklı TUTARLI kararı LP offset dış sınırıyla doğrulandı. 750 arızalı TUTARLI kararı bağımsız örnek kutusu sınırıyla doğrulandı. Aynı koşu R=1 ve R=3 için ayrı karar verebilir.

Her hücrede tohumlar 410000–410199. `cal-machine-complete/cells.jsonl` her tohum için t*, ilk sayılan alarm, dış offset aralığı ve iki R kararını içeriyor.

| Hücre / kol | TUTARSIZ | TUTARLI R=1 | TUTARLI R=3 |
| --- | ---: | ---: | ---: |
| healthy/E0 | 0 | 0 | 96 |
| healthy/E1 | 0 | 0 | 96 |
| offset_1/E0 | 50 | 0 | 102 |
| offset_1/E1 | 50 | 0 | 102 |
| offset_3/E0 | 144 | 0 | 0 |
| offset_3/E1 | 144 | 0 | 0 |
| jump_0.2/E0 | 199 | 0 | 1 |
| jump_0.2/E1 | 199 | 0 | 1 |
| jump_0.5/E0 | 200 | 0 | 0 |
| jump_0.5/E1 | 200 | 0 | 0 |
| jump_1/E0 | 200 | 0 | 0 |
| jump_1/E1 | 200 | 0 | 0 |
| jump_2/E0 | 200 | 0 | 0 |
| jump_2/E1 | 200 | 0 | 0 |
| jump_5/E0 | 200 | 0 | 0 |
| jump_5/E1 | 200 | 0 | 0 |
| drift_0.0005/E0 | 76 | 0 | 124 |
| drift_0.0005/E1 | 76 | 0 | 124 |
| drift_0.001/E0 | 150 | 50 | 50 |
| drift_0.001/E1 | 150 | 50 | 50 |
| drift_0.002/E0 | 200 | 0 | 0 |
| drift_0.002/E1 | 200 | 0 | 0 |
| drift_0.005/E0 | 200 | 0 | 0 |
| drift_0.005/E1 | 200 | 0 | 0 |
| drift_0.02/E0 | 200 | 0 | 0 |
| drift_0.02/E1 | 200 | 0 | 0 |
| drift_0.1/E0 | 200 | 0 | 0 |
| drift_0.1/E1 | 200 | 0 | 0 |
| noise_x2/E0 | 200 | 0 | 0 |
| noise_x2/E1 | 200 | 0 | 0 |
| noise_x4/E0 | 200 | 0 | 0 |
| noise_x4/E1 | 200 | 0 | 0 |
| stuck/E0 | 0 | 0 | 96 |
| stuck/E1 | 200 | 0 | 0 |
| gain_0.01/E0 | 200 | 0 | 0 |
| gain_0.01/E1 | 200 | 0 | 0 |
| gain_0.05/E0 | 200 | 0 | 0 |
| gain_0.05/E1 | 200 | 0 | 0 |

Oracle ile eş 1.900 koşuda oracle’ın tutarsız bulduğu 1544 koşunun 0’sında makine alarm vermedi. Oracle’ın tutarlı bulduğu koşularda 0 ters karar görüldü.

Sertifikalı oracle t* bulunan gecikme örneklerinde 310 ortak alarm, 0 makine alarmı olmayan koşu, 0 oracle’dan erken makine alarmı. Ortak alarmlarda makine − oracle farkı en az 0 s, medyan 0 s, en çok 963 s. Gecikme karşılaştırmasında 0 UNKNOWN dışarıda.

## Modelsiz baseline’lar

- **OBSERVED.** `91bda17` protokolün DMREDA referansını değiştirmeden ekledi. SHA-256 `0b8bffc7466b7dc67f353415a610edc668c50ac21db0d239fe885c49bbceef3e` protokoldeki önekle eşleşiyor. D/G skor adaptörü referansın `D_or_G` hızlı kapısını kullanıyor. CUSUM iki yönlü ve `y`’nin birinci farklarını tüketiyor. İki baseline da yalnız sonlu sensör ölçümleri alıyor. Değerlendirme en erken 300. örnekte başlıyor.
- **OBSERVED.** `410000` ve `410197` üzerinde 20’şer ikiz skor karşılaştırması. Çiftler arası azami skor farkı DMREDA’da `1.02e-12`, CUSUM’da `4.27e-14`. 600 örnekli önekle tam diziden alınan ilk 600 skor arasında fark sıfır. CUSUM `allowance=0` bu duman testi için kullanıldı. TRAIN eşiği veya P8 kararı üretilmedi.
- **UNKNOWN.** Dondurulmuş v2 metni CUSUM allowance değerini ve DMREDA’nın hangi skaler skorunun eşiğe gireceğini belirtmiyor. Skor adaptörü ve CUSUM arayüzü hazır. P1’in kalibre edilmiş baseline karar eşliği ve P8, TRAIN bütçesi kurulunca değerlendirilebilir.

## Matematiksel açıklar ve sonraki adım

- **HYPOTHESIS.** Mac’teki IPM çağrısı bir IPX durumundan sonra simplex toparlamasına düşmüş olabilir. Çağrı yığını simplex yolunu doğruluyor. IPX’in o denemede döndürdüğü iç durum **UNKNOWN**.
- **DERIVED.** P6, sağlıklı koşulun iç offset tanığı ve dış offset sınırını ayrı gerektiriyor. R=1 için CAL’de öngörülen pozitif bölgeye düşen koşu sayısı sıfır. R=3 için δ genişliğindeki bant dışı sonuçlar CAL gözlemidir. Bu koşulların genel yeterliliği **UNKNOWN**.
- **OBSERVED.** P7’de erken tutarsız 40 koşunun 25’inde arıza anı ile belirtilen komut değişimi arasında yeni bir komut adımı yoktu. 35 erken koşuda arıza anına göre ölçüm farkı, izinli ortam hızı ve gürültü toplamını tek başına aştı. Gerçek `z` dizisi, takılma ayrışımıyla `7.11e-15` °C düzeyinde örtüştü. Seed bazlı kanıt `cal-p7-diagnostics.jsonl` dosyasında.
- Önce modelsiz skor ve CUSUM allowance açıklığını kayda bağla. TRAIN kullanımı açılırsa kayıtlı sağlıklı TRAIN tohumlarında maksimum skor artı %5 eşiğini kur ve dondur. P8 ile baseline ikiz kararlarını bundan sonra değerlendir. Bu devirde TRAIN veya FINAL üretilmedi. Protokol dosyası aynı kaldı ve GitHub’a push yapılmadı.

## Değişen kaynaklar ve testler

| Commit | Dosyalar ve iş |
| --- | --- |
| `c04305a` | `experiments/oracle/thermal_oracle.py`, `validate_cal.py`, `tests/test_thermal_oracle.py`. Alt süreç izolasyonu, primal/dual kontrolleri, offset tanıkları, CAL deneme kayıtları. |
| `4e87cd3` | Oracle ve oracle testleri. Bağımsız oran alt sınırı. |
| `af505b6`, `96cf74d` | `experiments/machine/`, `experiments/generators/thermal_twins.py`, makine testleri. Çevrimiçi aralık ve CAL karşılaştırmaları. |
| `91bda17` | `experiments/baselines/`, baseline testleri. Salt sensör skorları ve tam referans SHA-256 kontrolü. |
| `17db9aa` | Oracle ve oracle testleri. Komşu öneklerle gecikme sertifikası. |

**OBSERVED.** Son Arch sürümünde 20/20 birim testi geçti. Makinenin P3 sağlıklı referansı olan V0/P6 tablosu iki tam oracle koşusunda bayt düzeyinde aynı.

## Dosyalar

- Kodun son commit’i `17db9aa3dab30964a5d2b87c161b20a279927b1a`. Geliştirme dalının adı `codex/thermal-highs-isolation`.
- `SDTS-CAL-evidence.tar.gz` ham hücre ve tohum tablolarını, üç oracle taramasının solver kayıtlarını, Mac crash kanıtını, makine ve baseline ölçümlerini içerir. SHA-256 `53497a716b63c726beb4619b3d1758eb1570b439d907c70ead515b76e8c59cbb`.
- `SDTS-arch.bundle` yerel Git commit’lerini ve bu devir kaydını taşır. Önkoşulu `c21f152cf49c48feb90c6c60bbb3636ebe9cbd43`.
