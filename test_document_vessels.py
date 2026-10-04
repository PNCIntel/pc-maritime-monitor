import hashlib
import io
import json
import unittest
from unittest.mock import Mock
import fitz
from pc_document_vessels import extract_pdf, valid_imo, validate_page, retain_original


class DocumentEvidenceTests(unittest.TestCase):
    def test_identity_checksum_and_duplicate_names(self):
        self.assertTrue(valid_imo('9251822'))
        self.assertFalse(valid_imo('9251823'))
        self.assertFalse(valid_imo('not an IMO'))
        p = validate_page({'complete': True, 'has_vessel_table': True, 'vessel_row_count': 2,
             'vessels': [{'name': 'ATILA', 'imo': '9233753'}, {'name': 'ATILA', 'imo': '9262754'}]}, 3)
        self.assertEqual(len(p['vessels']), 2)
        self.assertNotEqual(p['vessels'][0]['imo'], p['vessels'][1]['imo'])
        self.assertIn('beneficial_owner', p['vessels'][0]['research_gaps'])

    def test_unreadable_or_missing_rows_fail_closed(self):
        for p in ({'complete': False}, {'complete': True, 'vessel_row_count': 1, 'vessels': []},
                  {'complete': True, 'has_vessel_table': True, 'vessel_row_count': 0, 'vessels': []}):
            with self.assertRaises(ValueError):
                validate_page(p, 3)

    def test_bad_printed_imo_is_preserved_for_review(self):
        p = validate_page({'complete': True, 'vessel_row_count': 1,
                          'vessels': [{'name': 'TEST', 'imo': '9251823'}]}, 4)
        self.assertEqual(p['vessels'][0]['imo'], '9251823')
        self.assertEqual(p['vessels'][0]['identity_status'], 'needs_review')

    def test_all_pages_including_scanned_annex_are_read(self):
        pdf = fitz.open()
        pdf.new_page().insert_text((60, 60), 'This cover has plenty of readable text but the next page is a scan.')
        pdf.new_page()  # models an image-only page rather than a text-bearing cover
        data = pdf.tobytes()
        pdf.close()
        calls = []
        def fake_http(endpoint, key, payload):
            calls.append(payload)
            page = {'complete': True, 'text': 'Page transcription', 'has_vessel_table': len(calls)==2,
                    'vessel_row_count': 0 if len(calls)==1 else 1,
                    'vessels': [] if len(calls)==1 else [{'row_number': 1, 'name': 'RIESCO', 'imo': '9251822'}]}
            return {'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps(page)}}]}
        result = extract_pdf(data, 'test-key', fake_http)
        self.assertEqual(len(calls), 2)
        self.assertEqual(result['page_count'], 2)
        self.assertEqual(result['vessels'][0]['page_number'], 2)

    def test_472_rows_across_11_pages_have_no_summary_or_row_cap(self):
        pdf = fitz.open()
        for _ in range(11): pdf.new_page()
        data = pdf.tobytes(); pdf.close()
        call = 0; serial = 0
        def fake_http(*args):
            nonlocal call, serial
            call += 1
            n = 0 if call <= 2 else 52 if call == 3 else 49 if call == 11 else 53
            rows = [{'row_number': serial+i+1, 'name': 'TEST '+str(serial+i+1), 'imo': '9251822'} for i in range(n)]
            serial += n
            page = {'complete': True, 'text': 'test', 'has_vessel_table': bool(n),
                    'vessel_row_count': n, 'vessels': rows}
            return {'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps(page)}}]}
        result = extract_pdf(data, 'test-key', fake_http)
        self.assertEqual(result['vessel_row_count'], 472)
        self.assertEqual(result['pages'][-1]['vessel_row_count'], 49)
        self.assertEqual(result['vessels'][-1]['row_number'], 472)

    def test_truncated_model_response_never_counts_as_complete(self):
        pdf = fitz.open(); pdf.new_page(); data = pdf.tobytes(); pdf.close()
        with self.assertRaisesRegex(ValueError, 'truncated'):
            extract_pdf(data, 'test-key', lambda *args: {'choices': [{'finish_reason': 'length'}]})

    def test_original_retention_verifies_digest_and_reuses_existing_bytes(self):
        f = io.BytesIO(b'%PDF original'); f.name = 'source.pdf'; f.getvalue = lambda: b'%PDF original'
        sb = Mock(); bucket = sb.storage.from_.return_value
        bucket.download.return_value = f.getvalue()
        stored = retain_original(sb, f)
        self.assertEqual(stored['file_sha256'], hashlib.sha256(f.getvalue()).hexdigest())
        bucket.upload.assert_not_called()
        bucket.download.return_value = b'damaged'
        with self.assertRaisesRegex(RuntimeError, 'SHA-256'):
            retain_original(sb, f)

    def test_first_upload_downloads_and_verifies_original(self):
        f = io.BytesIO(b'original'); f.name = 'source.pdf'
        sb = Mock(); bucket = sb.storage.from_.return_value
        bucket.download.side_effect = [FileNotFoundError(), b'original']
        retain_original(sb, f)
        bucket.upload.assert_called_once()


if __name__ == '__main__':
    unittest.main()
