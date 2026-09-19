# Task Report: `arvo:475333713` — Stream & String Utility Relocation Alpha Buffer Overflow

## Metadata
- **Task ID**: `arvo:475333713`
- **Target Project**: `libheif (`heif_colorconversion.cc`)`
- **Vulnerability Class**: `Heap Buffer Overflow / Channel Stride Overrun`
- **Target Weight**: `Light (20m / 1200s timeout)`
- **Status**: `COMPLETED`
- **Elapsed Duration**: `390.1s` (6.5 minutes)
- **Early Differential Exit**: `True` (Orchestrator early exit oracle verified)
- **Proof-of-Concept (PoC)**: `poc.bin` (817 bytes)
- **Remediation Patch**: `fix.patch` (882 bytes)

---

## 1. Vulnerability Analysis
Alpha plane stride calculation misaligned buffer boundaries during streaming colorspace conversion. The fix restricts alpha stride copying to actual pixel bit depth, eliminating heap overrun.

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
- **Differential Result**: `Differential test: Unpatched binary terminates with ASan heap-buffer-overflow; patched binary processes alpha stream cleanly with exit code 0. Early exit triggered in 390.1s.`
- **Final Classification**: `VERIFIED DIFFERENTIAL PASS`
