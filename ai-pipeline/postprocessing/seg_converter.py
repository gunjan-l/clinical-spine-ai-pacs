"""
Production-grade NIfTI to DICOM SEG converter
Generates DICOM SEG objects for PACS integration
"""

import os
import json
import subprocess
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SEGConverter:
    """
    Convert NIfTI segmentations to DICOM SEG format
    Optimized for TotalSpineSeg output integration
    """

    def __init__(self, metadata_template_path=None):
        self.metadata_template_path = metadata_template_path
        self._verify_itk_converter()

    def _verify_itk_converter(self):
        """Verify itkimage2segimage tool is available"""
        try:
            result = subprocess.run(['itkimage2segimage', '--help'],
                                    capture_output=True, text=True)
            if result.returncode not in [0, 1]:  # Help often returns 1
                raise RuntimeError("itkimage2segimage not found")
        except FileNotFoundError:
            raise RuntimeError(
                "itkimage2segimage not found. Install from plastimatch or Slicer"
            )

    def load_metadata_template(self, study_info=None):
        """
        Load DICOM SEG metadata template with study-specific information

        Args:
            study_info: Dict with patient/study details
        """
        default_metadata = {
            "ContentCreatorName": "SpineAISystem",
            "ClinicalTrialSeriesID": "SpineSegmentation",
            "ClinicalTrialTimePointID": "1",
            "SeriesDescription": "AI Spine Segmentation",
            "SeriesNumber": "1001",
            "InstanceNumber": "1",
            "segmentAttributes": [[]],
            "BodyPart": "SPINE",
            "SegmentLabel": "SpineSegmentation"
        }

        if study_info:
            default_metadata.update(study_info)

        return default_metadata

    def convert_to_seg(self, input_nifti, input_dicom_dir, output_seg, metadata=None):
        """
        Convert NIfTI segmentation to DICOM SEG

        Args:
            input_nifti: Path to NIfTI segmentation file
            input_dicom_dir: Path to source DICOM directory (for reference)
            output_seg: Path for output DICOM SEG file
            metadata: Optional metadata dict
        """
        logger.info("Converting NIfTI to DICOM SEG")
        logger.info(f"Input NIfTI: {input_nifti}")
        logger.info(f"Reference DICOM: {input_dicom_dir}")
        logger.info(f"Output SEG: {output_seg}")

        # Validate inputs
        if not os.path.isfile(input_nifti):
            raise ValueError(f"NIfTI file not found: {input_nifti}")

        if not os.path.isdir(input_dicom_dir):
            raise ValueError(f"DICOM directory not found: {input_dicom_dir}")

        # Create output directory
        os.makedirs(os.path.dirname(output_seg), exist_ok=True)

        # Generate metadata if not provided
        if metadata is None:
            metadata = self.load_metadata_template()

        # Write metadata to temporary file
        metadata_path = output_seg.replace('.dcm', '_metadata.json')
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)

        try:
            # Build command
            cmd = [
                "itkimage2segimage",
                "--inputImageList", input_nifti,
                "--inputDICOMDirectory", input_dicom_dir,
                "--outputDICOM", output_seg,
                "--inputMetadata", metadata_path,
                "--skip"
            ]

            logger.info(f"Running: {' '.join(cmd)}")

            result = subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True
            )

            logger.info("DICOM SEG conversion successful")

            # Clean up metadata file
            if os.path.exists(metadata_path):
                os.remove(metadata_path)

            return {
                'status': 'success',
                'output_file': output_seg,
                'log': result.stdout
            }

        except subprocess.CalledProcessError as e:
            logger.error(f"Conversion failed: {e.stderr}")
            raise RuntimeError(f"itkimage2segimage failed: {e.stderr}")
        finally:
            # Cleanup
            if os.path.exists(metadata_path):
                os.remove(metadata_path)


def main():
    """CLI interface for SEG conversion"""
    parser = argparse.ArgumentParser(
        description="Convert NIfTI to DICOM SEG for PACS integration",
        epilog="Example: python seg_converter.py input.nii.gz dicom_dir output.dcm"
    )

    parser.add_argument("nifti_file", help="Input NIfTI segmentation")
    parser.add_argument("dicom_dir", help="Reference DICOM directory")
    parser.add_argument("output_seg", help="Output DICOM SEG file")
    parser.add_argument("--metadata", help="JSON metadata file path")

    args = parser.parse_args()

    try:
        converter = SEGConverter()

        metadata = None
        if args.metadata:
            with open(args.metadata, 'r') as f:
                metadata = json.load(f)

        result = converter.convert_to_seg(
            args.nifti_file,
            args.dicom_dir,
            args.output_seg,
            metadata
        )

        print(f"\nDICOM SEG created: {result['output_file']}")

    except Exception as e:
        logger.error(f"Conversion failed: {e}")
        exit(1)


if __name__ == "__main__":
    main()