"""The curated probe's endpoint allowlist also sees budgeted transports."""
import ast
import unittest
from unittest.mock import patch

import test_curated_probe_leak as leak


class BudgetedTransportGuard(unittest.TestCase):
    def test_budgeted_and_direct_requests_keep_the_same_target_checks(self):
        case = leak.NoPaidCallsAndNoFetching()
        tree = ast.parse('blog_reads.get(url, getter=requests.get)\nrequests.post(site)')
        with patch.object(case, '_tree', return_value=tree):
            self.assertEqual(case._request_urls(), [(1, {'url'}), (2, {'site'})])
            with self.assertRaises(AssertionError):
                case.test_every_request_target_is_a_declared_endpoint()
