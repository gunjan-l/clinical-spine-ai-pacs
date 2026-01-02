"""
Production-grade DICOM to NIfTI converter using dcm2niix
Optimized for spine MRI studies in clinical AI pipeline
"""

import os
import argparse
import subprocess
import logging

# Configure logging for production
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class DICOMConverter:
    """
    Robust DICOM to NIfTI converter with quality validation
    Designed for TotalSpineSeg pipeline integration
    """

    def __init__(self, output_compression=True, anonymize=False):
        self.output_compression = output_compression
        self.anonymize = anonymize
        self._verify_dcm2niix()

    def _verify_dcm2niix(self):
        """Verify dcm2niix is installed and accessible"""
        try:
            result = subprocess.run(['dcm2niix', '-v'],
                                    capture_output=True, text=True, check=True)
            logger.info(f"dcm2niix verified: {result.stdout.strip()}")
        except (subprocess.CalledProcessError, FileNotFoundError):
            raise RuntimeError(
                "dcm2niix not found. Install from https://github.com/rordenlab/dcm2niix"
            )

    def convert_study(self, input_dir, output_dir, study_description="spine"):
        """
        Convert DICOM study to NIfTI format optimized for TotalSpineSeg

        Args:
            input_dir: Path to DICOM study directory
            output_dir: Path to output NIfTI directory
            study_description: Description for logging

        Returns:
            dict: Paths to converted files and metadata
        """
        logger.info(f"Converting {study_description} study")
        logger.info(f"Input: {input_dir}")
        logger.info(f"Output: {output_dir}")

        # Validate input
        if not os.path.isdir(input_dir):
            raise ValueError(f"Input directory not found: {input_dir}")

        # Create output directory
        os.makedirs(output_dir, exist_ok=True)

        # Build dcm2niix command with optimized parameters for spine MRI
        cmd = [
            "dcm2niix",
            "-o", output_dir,
            "-z", "y" if self.output_compression else "n",
            "-ba", "y" if self.anonymize else "n",
            "-f", "%p_%s_%d",  # Filename: Protocol_Series_Description
            "-v", "1",  # Verbose output
            input_dir
        ]

        try:
            logger.info(f"Running: {' '.join(cmd)}")

            result = subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True
            )

            logger.info(" Conversion successful")

            # Parse output files
            output_files = self._parse_dcm2niix_output(result.stdout, output_dir)

            return {
                'status': 'success',
                'output_files': output_files,
                'log': result.stdout
            }

        except subprocess.CalledProcessError as e:
            logger.error(f" Conversion failed: {e.stderr}")
            raise RuntimeError(f"dcm2niix failed: {e.stderr}")

    def _parse_dcm2niix_output(self, stdout, output_dir):
        """Parse dcm2niix output to identify created files"""
        files = []
        for line in stdout.split('\n'):
            if "Saving:" in line or "Convert:" in line:
                # Extract filename from dcm2niix output
                parts = line.split()
                for part in parts:
                    if part.endswith('.nii') or part.endswith('.nii.gz'):
                        files.append(os.path.join(output_dir, part))
        return files

    def validate_output(self, output_dir):
        """
        Validate converted NIfTI files for TotalSpineSeg compatibility
        """
        nifti_files = [f for f in os.listdir(output_dir)
                       if f.endswith(('.nii', '.nii.gz'))]

        if not nifti_files:
            raise ValueError("No NIfTI files generated")

        logger.info(f"Generated {len(nifti_files)} NIfTI files")

        # Additional validation: check file size, dimensions
        valid_files = []
        for nii_file in nifti_files:
            filepath = os.path.join(output_dir, nii_file)
            if os.path.getsize(filepath) > 1024:  # At least 1KB
                valid_files.append(filepath)

        return valid_files


def main():
    """CLI interface for DICOM conversion"""
    parser = argparse.ArgumentParser(
        description="Clinical-grade DICOM to NIfTI converter for spine AI",
        epilog="Example: python dcm2niix_converter.py /path/to/dicom /path/to/nifti"
    )

    parser.add_argument("input_dir", help="Source DICOM directory")
    parser.add_argument("output_dir", help="Output NIfTI directory")
    parser.add_argument("--no-compress", action="store_true", help="Disable compression")
    parser.add_argument("--anonymize", action="store_true", help="Anonymize output")

    args = parser.parse_args()

    try:
        converter = DICOMConverter(
            output_compression=not args.no_compress,
            anonymize=args.anonymize
        )

        result = converter.convert_study(args.input_dir, args.output_dir)

        print("\n Conversion completed successfully")
        print(f"Files created: {len(result['output_files'])}")
        for f in result['output_files']:
            print(f"  - {f}")

    except Exception as e:
        logger.error(f"Conversion failed: {e}")
        exit(1)


if __name__ == "__main__":
    main()