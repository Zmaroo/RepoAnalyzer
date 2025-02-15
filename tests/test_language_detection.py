import os
import unittest
import json
import datetime
from parsers.file_parser import detect_language, process_file
from parsers.language_mapping import EXTENSION_TO_LANGUAGE, SPECIAL_FILENAMES, get_language_for_file
from utils.logger import log

class TestLanguageDetection(unittest.TestCase):
    """
    End-to-end test for file-based language detection and processing.
    
    This test iterates over sample files, verifies that detect_language returns the expected language,
    and ensures that process_file successfully processes the file.
    """
    
    @classmethod
    def setUpClass(cls):
        # Directory containing sample files for testing.
        base_dir = os.path.dirname(__file__)
        cls.sample_dir = os.path.join(base_dir, "test_parse")
        cls.data_dir = os.path.join(cls.sample_dir, "data")
        cls.output_dir = os.path.join(base_dir, "test_outputs")
        
        # Ensure directories exist.
        for directory in [cls.output_dir, cls.sample_dir, cls.data_dir]:
            os.makedirs(directory, exist_ok=True)
        
        # Build expected language map.
        cls.expected_languages = {}
        cls.unsupported_extensions = set()
        
        for directory in [cls.sample_dir, cls.data_dir]:
            for file in os.listdir(directory):
                file_path = os.path.join(directory, file)
                if os.path.isfile(file_path):
                    # Check special filenames.
                    if file in SPECIAL_FILENAMES:
                        expected = SPECIAL_FILENAMES[file]
                    else:
                        expected = get_language_for_file(file_path)
                    cls.expected_languages[file] = expected
                    _, ext = os.path.splitext(file)
                    if ext and expected is None and file not in SPECIAL_FILENAMES:
                        cls.unsupported_extensions.add(ext)
    
    def setUp(self):
        # Log unsupported extensions if any.
        if self.unsupported_extensions:
            print("\nWarning: Found files with unsupported extensions:")
            for ext in sorted(self.unsupported_extensions):
                print(f"  {ext}")
            unsupported_file = os.path.join(self.output_dir, "unsupported_languages.json")
            with open(unsupported_file, "w", encoding="utf-8") as f:
                json.dump({
                    "unsupported_extensions": sorted(list(self.unsupported_extensions)),
                    "timestamp": str(datetime.datetime.now())
                }, f, indent=4)
            print(f"List of unsupported extensions written to: {unsupported_file}")
    
    def test_detect_and_process_files(self):
        log("Starting file processing test", level="debug")
        
        # Languages that are handled by our custom parsers.
        custom_languages = {"yaml", "ocaml", "ocaml_interface", "editorconfig",
                            "plaintext", "env", "graphql", "nim", "markdown"}
        
        processed_languages = set()
        failed_files = []
        
        # Process files from both sample and data directories.
        for directory in [self.sample_dir, self.data_dir]:
            for file_name, expected_lang in self.expected_languages.items():
                file_path = os.path.join(directory, file_name)
                if not os.path.isfile(file_path):
                    continue
                
                with self.subTest(file=file_name):
                    detected_language = detect_language(file_path)
                    self.assertEqual(
                        detected_language,
                        expected_lang,
                        f"Language detection for {file_name} returned '{detected_language}', expected '{expected_lang}'."
                    )
                    
                    processed_data = process_file(file_path)
                    
                    # If a language is detected, we expect processing to succeed.
                    if detected_language is not None:
                        self.assertIsNotNone(
                            processed_data,
                            f"Processing file {file_name} should not return None for supported language '{detected_language}'."
                        )
                        
                        # Validate that the processed data includes key fields.
                        self.assertEqual(
                            processed_data.get("language"),
                            detected_language,
                            f"Processed language for {file_name} is '{processed_data.get('language')}', expected '{detected_language}'."
                        )
                        self.assertIn("ast_data", processed_data, f"'ast_data' should be in the processed output for {file_name}.")
                        self.assertIn("ast_json", processed_data, f"'ast_json' should be in the processed output for {file_name}.")
                        
                        processed_languages.add(detected_language)
                        
                        out_file = os.path.join(self.output_dir, f"{file_name}_processed.json")
                        with open(out_file, "w", encoding="utf-8") as f:
                            json.dump(processed_data, f, indent=4)
                        print(f"Processing output for {file_name} written to: {out_file}")
                    else:
                        print(f"Skipping {file_name} - no language detected.")
                        failed_files.append(file_name)
        
        # Warn if some supported languages were not tested.
        supported_languages = set(EXTENSION_TO_LANGUAGE.values())
        untested_languages = supported_languages - processed_languages
        if untested_languages:
            print("\nWarning: The following supported languages were not tested:")
            for lang in sorted(untested_languages):
                print(f"  {lang}")
            print("Consider adding test files for these languages.\n")
        
        # If any files expected to be processed failed, fail the test.
        if failed_files:
            self.fail(f"Failed to process files for: {', '.join(sorted(failed_files))}")

if __name__ == "__main__":
    unittest.main()