#!/usr/bin/env python3
"""Example: Complete spine segmentation pipeline"""

from ai_pipeline.preprocessing.dcm2niix_converter import DICOMConverter
from ai_pipeline.inference.spine_segmentation import TotalSpineSegInference
from ai_pipeline.postprocessing.seg_converter import SEGConverter


def process_spine_study(dicom_input, work_dir, final_output):
    """Complete pipeline: DICOM → NIfTI → AI → DICOM SEG"""

    # Stage 1: DICOM to NIfTI
    print("=" * 60)
    print("STAGE 1: DICOM Conversion")
    print("=" * 60)

    converter = DICOMConverter()
    nifti_result = converter.convert_study(dicom_input, f"{work_dir}/nifti")

    # Stage 2: AI Segmentation
    print("\n" + "=" * 60)
    print("STAGE 2: AI Segmentation")
    print("=" * 60)

    inference = TotalSpineSegInference()
    ai_results = inference.run_inference(
        nifti_result['output_dir'],
        f"{work_dir}/ai_output"
    )

    # Stage 3: DICOM SEG Generation
    print("\n" + "=" * 60)
    print("STAGE 3: DICOM SEG Conversion")
    print("=" * 60)

    seg_converter = SEGConverter()
    seg_result = seg_converter.convert_to_seg(
        f"{work_dir}/ai_output/step2_output/study.nii.gz",
        dicom_input,
        final_output
    )

    print("\n COMPLETE PIPELINE FINISHED!")
    print(f"📄 Final DICOM SEG: {final_output}")


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 4:
        print("Usage: python pipeline.py <dicom_input> <work_dir> <final_output>")
        sys.exit(1)

    process_spine_study(sys.argv[1], sys.argv[2], sys.argv[3])