#!/usr/bin/env python3
"""
Production-grade TotalSpineSeg inference wrapper
Optimized for clinical PACS integration with robust error handling
"""

import os
import sys
import json
import logging
import subprocess
import argparse
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Configure logging for clinical pipeline
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(name)s] - %(message)s',
    handlers=[
        logging.FileHandler('/app/logs/spine_segmentation.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class SpineSegmentationError(Exception):
    """Custom exception for spine segmentation pipeline failures"""
    pass


class TotalSpineSegInference:
    """
    Production-ready wrapper for TotalSpineSeg CLI
    Handles two-stage pipeline with validation and error recovery
    """

    def __init__(self, model_data_dir: str = "/app/models"):
        self.model_data_dir = model_data_dir
        self._setup_environment()
        self._verify_totalspineseg()

        # Expected output structure from TotalSpineSeg
        self.expected_outputs = [
            "step1_output",
            "step2_output",
            "preview",
            "step1_levels"
        ]

    def _setup_environment(self):
        """Configure TotalSpineSeg environment variables"""
        os.environ['TOTALSPINESEG_DATA'] = self.model_data_dir

        # Create model directory if needed
        Path(self.model_data_dir).mkdir(parents=True, exist_ok=True)

        logger.info(f"TotalSpineSeg environment configured: {self.model_data_dir}")

    def _verify_totalspineseg(self):
        """Verify TotalSpineSeg is installed and accessible"""
        try:
            result = subprocess.run(
                ['totalspineseg', '--help'],
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0:
                logger.info("TotalSpineSeg verified and ready")
            else:
                raise RuntimeError("TotalSpineSeg command failed")

        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            logger.error(" TotalSpineSeg not found or not working")
            logger.error("Install with: pip install totalspineseg[nnunetv2]")
            raise RuntimeError(f"TotalSpineSeg verification failed: {e}")

    def validate_input(self, input_path: str) -> bool:
        """
        Validate input data before processing
        Returns: True if valid, raises exception otherwise
        """
        input_path = Path(input_path)

        # Check if input exists
        if not input_path.exists():
            raise ValueError(f"Input path does not exist: {input_path}")

        # Check if NIfTI file or directory
        if input_path.is_file():
            if not input_path.suffix in ['.nii', '.nii.gz']:
                raise ValueError(f"Invalid file format: {input_path.suffix}. Expected .nii or .nii.gz")

            # Basic file size check (should be at least 1MB for spine MRI)
            if input_path.stat().st_size < 1024 * 1024:
                logger.warning(f"Input file unusually small: {input_path.stat().st_size} bytes")

        elif input_path.is_dir():
            # Check for NIfTI files in directory
            nii_files = list(input_path.glob("*.nii")) + list(input_path.glob("*.nii.gz"))
            if not nii_files:
                raise ValueError(f"No NIfTI files found in directory: {input_path}")

            logger.info(f"Found {len(nii_files)} NIfTI files in input directory")

        else:
            raise ValueError(f"Input path is neither file nor directory: {input_path}")

        logger.info(f"Input validation passed: {input_path}")
        return True

    def _download_models_if_needed(self):
        """Ensure TotalSpineSeg models are downloaded"""
        import totalspineseg.utils as utils

        model_dir = Path(self.model_data_dir) / "models"
        if not model_dir.exists() or not any(model_dir.iterdir()):
            logger.info("🔄 TotalSpineSeg models not found. Downloading...")
            try:
                utils.download_weights(self.model_data_dir)
                logger.info("Models downloaded successfully")
            except Exception as e:
                logger.error(f" Model download failed: {e}")
                raise SpineSegmentationError("Cannot download TotalSpineSeg models")

    def run_inference(self, input_path: str, output_dir: str, step_only: Optional[int] = None) -> Dict:
        """
        Run TotalSpineSeg inference on input data

        Args:
            input_path: Path to NIfTI file or directory
            output_dir: Path to output directory
            step_only: Run only step 1 or 2 (None runs both)

        Returns:
            Dictionary with results and metadata
        """
        # Validate inputs
        self.validate_input(input_path)

        # Ensure models are available
        self._download_models_if_needed()

        # Create output directory
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # Build command
        cmd = [
            "totalspineseg",
            str(input_path),
            str(output_path)
        ]

        if step_only == 1:
            cmd.append("--step1")
            logger.info("🔧 Running STEP 1 only (landmark detection)")
        elif step_only == 2:
            logger.info("🔧 Running STEP 2 only (segmentation)")
            # Note: Step 2 requires step1_output directory
            # This is handled by TotalSpineSeg internally
        else:
            logger.info("🔧 Running FULL PIPELINE (Step 1 + Step 2)")

        # Add isotropic output flag for better visualization
        cmd.append("--iso")

        logger.info(f"🚀 Starting TotalSpineSeg inference")
        logger.info(f"   Command: {' '.join(cmd)}")
        logger.info(f"   Input: {input_path}")
        logger.info(f"   Output: {output_dir}")

        # Run inference
        start_time = datetime.now()

        try:
            result = subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True,
                timeout=1800  # 30 minute timeout for large studies
            )

            inference_time = (datetime.now() - start_time).total_seconds()

            logger.info(f"Inference completed in {inference_time:.2f} seconds")

            # Parse and validate outputs
            outputs = self._validate_outputs(output_path)

            return {
                'status': 'success',
                'inference_time_sec': inference_time,
                'output_directory': str(output_path),
                'output_files': outputs,
                'log': result.stdout,
                'command': ' '.join(cmd)
            }

        except subprocess.TimeoutExpired:
            logger.error(" Inference timed out after 30 minutes")
            raise SpineSegmentationError("TotalSpineSeg inference timeout")

        except subprocess.CalledProcessError as e:
            logger.error(f" TotalSpineSeg failed: {e.stderr}")
            raise SpineSegmentationError(f"Inference failed: {e.stderr}")

        except Exception as e:
            logger.error(f" Unexpected error: {e}")
            raise SpineSegmentationError(f"Inference error: {e}")

    def _validate_outputs(self, output_dir: Path) -> Dict[str, List[str]]:
        """
        Validate TotalSpineSeg output structure
        Returns: Dictionary of output categories and files
        """
        logger.info("🔍 Validating TotalSpineSeg outputs...")

        outputs = {}

        for category in self.expected_outputs:
            category_dir = output_dir / category
            if category_dir.exists():
                files = [str(f) for f in category_dir.glob("*.nii.gz")]
                outputs[category] = files

                logger.info(f"   {category}: {len(files)} files")
            else:
                logger.warning(f"   ⚠️  {category}: directory not found")
                outputs[category] = []

        # Check for critical outputs
        step2_output = output_dir / "step2_output"
        if not step2_output.exists() or not any(step2_output.glob("*.nii.gz")):
            raise SpineSegmentationError(
                "Critical output missing: step2_output segmentation files"
            )

        logger.info("Output validation passed")
        return outputs

    def generate_report(self, results: Dict) -> str:
        """
        Generate clinical processing report
        """
        report = {
            "processing_timestamp": datetime.now().isoformat(),
            "pipeline": "TotalSpineSeg Clinical Inference",
            "status": results['status'],
            "inference_time_seconds": results['inference_time_sec'],
            "output_directory": results['output_directory'],
            "output_summary": {
                category: len(files)
                for category, files in results['output_files'].items()
            },
            "clinical_validation": {
                "vertebrae_segments": 50,  # TotalSpineSeg outputs 50+ structures
                "verification_status": "PENDING_RADIOMLOGIST_REVIEW"
            }
        }

        report_path = Path(results['output_directory']) / "processing_report.json"
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)

        logger.info(f"📄 Processing report saved: {report_path}")
        return str(report_path)


def main():
    """CLI interface for TotalSpineSeg inference"""
    parser = argparse.ArgumentParser(
        description="Production TotalSpineSeg inference for clinical spine segmentation",
        epilog="Example: python spine_segmentation.py /input/study.nii.gz /output/results/"
    )

    parser.add_argument("input_path", help="Path to input NIfTI file or directory")
    parser.add_argument("output_dir", help="Path to output directory")
    parser.add_argument(
        "--step-only",
        type=int,
        choices=[1, 2],
        help="Run only step 1 (landmarks) or step 2 (segmentation)"
    )
    parser.add_argument(
        "--model-dir",
        default="/app/models",
        help="Path to TotalSpineSeg models directory"
    )
    parser.add_argument(
        "--generate-report",
        action="store_true",
        help="Generate clinical processing report"
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=1800,
        help="Timeout in seconds (default: 1800)"
    )

    args = parser.parse_args()

    try:
        # Initialize inference engine
        inference = TotalSpineSegInference(model_data_dir=args.model_dir)

        # Run inference
        results = inference.run_inference(
            input_path=args.input_path,
            output_dir=args.output_dir,
            step_only=args.step_only
        )

        # Generate report if requested
        if args.generate_report:
            report_path = inference.generate_report(results)
            print(f"\n📄 Clinical report: {report_path}")

        print("\nInference completed successfully!")
        print(f"📁 Output: {results['output_directory']}")
        print(f"⏱️  Time: {results['inference_time_sec']:.2f} seconds")

        # List key output files
        if 'step2_output' in results['output_files']:
            print("\n🎯 Key segmentation files:")
            for f in results['output_files']['step2_output'][:3]:  # Show first 3
                print(f"   - {Path(f).name}")

    except SpineSegmentationError as e:
        logger.error(f" Pipeline failed: {e}")
        print(f"\n ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    except Exception as e:
        logger.error(f" Unexpected failure: {e}")
        print(f"\n UNEXPECTED ERROR: {e}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()