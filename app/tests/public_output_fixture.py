"""Explicit synthetic release-unit-test fixture; never runtime evidence."""
import hashlib


def passing_public_output(sha):
    return {'provenance': {'commit': sha, 'working_tree_diff_sha256': hashlib.sha256(b'').hexdigest()},
            'results': [{'case_id': f'UNIT-ONLY-{i}', 'http_status': 200,
                         'strict_pass': True, 'strict_failures': [],
                         'raw_response': {'answer': {'summary': 'Synthetic unit fixture'}},
                         'professional_default': {'passed': True},
                         'professional_expanded': {'passed': True},
                         'jury': {'overall_passed': True}} for i in range(60)]}
