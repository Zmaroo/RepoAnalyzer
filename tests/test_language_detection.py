import os
import unittest
import json
from parsers.file_parser import detect_language, process_file

class TestLanguageDetection(unittest.TestCase):
    """
    End-to-end test for file-based language detection and processing.
    
    This test iterates over sample files in the tests/test_parse directory,
    verifies that detect_language() returns the expected language based on file extensions,
    and, for supported files, ensures that process_file() successfully processes the file.
    
    Processing results (if available) are written to output files for manual inspection.
    """
    
    @classmethod
    def setUpClass(cls):
        # Directory containing sample files for testing.
        cls.sample_dir = os.path.join(os.path.dirname(__file__), "test_parse")
        # Directory for output files.
        cls.output_dir = os.path.join(os.path.dirname(__file__), "test_outputs")
        
        # Ensure the output directory exists.
        if not os.path.exists(cls.output_dir):
            os.makedirs(cls.output_dir)
        
        # Ensure the sample directory exists.
        if not os.path.exists(cls.sample_dir):
            os.makedirs(cls.sample_dir)
        
        # ---------------------------------------------------------------------
        # Build the expected_languages mapping dynamically based on the actual
        # files present in the test_parse directory.
        # ---------------------------------------------------------------------
        
        # Mapping from file extension to expected language.
        extension_map = {
            ".js": "javascript",
            ".jsx": "javascript",
            ".mjs": "javascript",
            ".ts": "typescript",
            ".tsx": "tsx",
            ".java": "java",
            ".c": "c",
            ".cpp": "cpp",
            # Add additional extensions as needed:
            ".py": "python",
            ".rb": "ruby",
            ".go": "go",
            ".php": "php",
        }
        
        # Manual overrides for specific file names or extensions.
        manual_overrides = {
            ".env": None,
            ".editorconfig": None,
            # You can add any other overrides here.
        }
        
        cls.expected_languages = {}
        # Iterate over every file in sample_dir and build the expected mapping.
        for file in os.listdir(cls.sample_dir):
            # Check if the file's name is directly overridden.
            if file in manual_overrides:
                expected = manual_overrides[file]
            else:
                # Get the extension.
                _, ext = os.path.splitext(file)
                # Check if the extension itself should be manually overridden.
                if ext in manual_overrides:
                    expected = manual_overrides[ext]
                else:
                    expected = extension_map.get(ext, None)
            cls.expected_languages[file] = expected

    def test_detect_and_process_files(self):
        for file_name, expected_lang in self.expected_languages.items():
            file_path = os.path.join(self.sample_dir, file_name)
            with self.subTest(file=file_name):
                # Verify language detection.
                detected_language = detect_language(file_path)
                self.assertEqual(
                    detected_language,
                    expected_lang,
                    f"Language detection for {file_name} returned {detected_language}, expected {expected_lang}."
                )
                
                # Process file using existing program logic.
                processed_data = process_file(file_path)
                
                if detected_language is not None:
                    self.assertIsNotNone(
                        processed_data,
                        f"Processing supported file {file_name} returned None."
                    )
                    self.assertEqual(
                        processed_data.get("language"),
                        detected_language,
                        f"Processed language for {file_name} is {processed_data.get('language')}, expected {detected_language}."
                    )
                    
                    # Write the processing output to a file for inspection.
                    out_file = os.path.join(self.output_dir, f"{file_name}_processed.json")
                    with open(out_file, "w", encoding="utf-8") as f:
                        json.dump(processed_data, f, indent=4)
                    print(f"Processing output for {file_name} written to: {out_file}")
                else:
                    self.assertIsNone(
                        processed_data,
                        f"Processing file {file_name} should return None for unsupported file types."
                    )
                    print(f"File {file_name} is not supported, as expected.")

if __name__ == "__main__":
    unittest.main() 