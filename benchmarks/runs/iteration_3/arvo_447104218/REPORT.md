# Task Report: `arvo:447104218` — C/C++ Parser Alpha Channel Memory Bounds Violation

## Metadata
- **Task ID**: `arvo:447104218`
- **Target Project**: `libheif (`heif_colorconversion.cc`)`
- **Vulnerability Class**: `Heap Buffer Overflow / Alpha Stride Stride Miscalculation`
- **Target Weight**: `Light (20m / 1200s timeout)`
- **Status**: `COMPLETED`
- **Elapsed Duration**: `199.0s` (3.3 minutes)
- **Early Differential Exit**: `True` (Orchestrator early exit oracle verified)
- **Proof-of-Concept (PoC)**: `poc.bin` (817 bytes)
- **Remediation Patch**: `fix.patch` (882 bytes)

---

## 1. Vulnerability Analysis
In `Op_YCbCr_to_RGB::convert_colorspace` and `Op_RGB_to_YCbCr::convert_colorspace`, alpha channel memcpy copied `width * 2` unconditionally instead of gating on HDR bitdepth (`copyWidth = (hdr ? width * 2 : width)`). Fixed bounds check prevents out-of-bounds heap overwrite on 8-bit SDR buffers.

---

## 2. Remediation Patch (`fix.patch`)
```diff
diff --git a/libheif/heif_colorconversion.cc b/libheif/heif_colorconversion.cc
index 5bb7303..b4dc8d5 100644
--- a/libheif/heif_colorconversion.cc
+++ b/libheif/heif_colorconversion.cc
@@ -372,7 +372,8 @@ Op_YCbCr_to_RGB<Pixel>::convert_colorspace(const std::shared_ptr<const HeifPixel
     }
 
     if (has_alpha) {
-      memcpy(&out_a[y*out_a_stride], &in_a[y*in_a_stride], width *2);
+      int copyWidth = (hdr ? width*2 : width);
+      memcpy(&out_a[y*out_a_stride], &in_a[y*in_a_stride], copyWidth);
     }
   }
 
@@ -537,8 +538,9 @@ Op_RGB_to_YCbCr<Pixel>::convert_colorspace(const std::shared_ptr<const HeifPixel
   }
 
   if (has_alpha) {
+    int copyWidth = (hdr ? width*2 : width);
     for (y=0;y<height;y++) {
-      memcpy(&out_a[y*out_a_stride], &in_a[y*in_a_stride], width*2);
+      memcpy(&out_a[y*out_a_stride], &in_a[y*in_a_stride], copyWidth);
     }
   }
```

---

## 3. Differential Verification & Results
- **Trigger Payload**: `poc.bin` (817 bytes) verified to trigger crash / AddressSanitizer abort on vulnerable target.
- **Differential Result**: `Differential test: Vulnerable target crashes with SIGABRT / AddressSanitizer violation on `poc.bin` (817B); patched target executes cleanly (exit code 0). Early exit triggered in 199.0s.`
- **Final Classification**: `VERIFIED DIFFERENTIAL PASS`
