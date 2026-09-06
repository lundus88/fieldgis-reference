import unittest
from connector_policy import authorize_connector_call


CONNECTOR = {
    'id':'sandbox-storage',
    'version':'1.0.0',
    'status':'certified',
    'ambient_credentials':False,
    'allowed_operations':['read','write','purchase'],
    'resource_scopes':['workspace/demo'],
    'high_impact_operations':['write'],
    'paid_operations':['purchase'],
}
GRANT = {'capabilities':['connector.invoke:sandbox-storage']}


class ConnectorPolicyTests(unittest.TestCase):
    def test_read_in_scope_allowed(self):
        out=authorize_connector_call(CONNECTOR,{'operation':'read','resource':'workspace/demo/file.txt'},GRANT)
        self.assertEqual(out['decision'],'ALLOW')
        self.assertFalse(out['secret_material_exposed'])
        self.assertFalse(out['ambient_credentials_used'])

    def test_out_of_scope_resource_denied(self):
        out=authorize_connector_call(CONNECTOR,{'operation':'read','resource':'workspace/other/file.txt'},GRANT)
        self.assertEqual(out['reason'],'RESOURCE_OUT_OF_SCOPE')

    def test_ungranted_connector_denied(self):
        out=authorize_connector_call(CONNECTOR,{'operation':'read','resource':'workspace/demo/file.txt'},{'capabilities':[]})
        self.assertEqual(out['reason'],'CONNECTOR_CAPABILITY_NOT_GRANTED')

    def test_paid_operation_requires_human_approval(self):
        out=authorize_connector_call(CONNECTOR,{'operation':'purchase','resource':'workspace/demo/item'},GRANT)
        self.assertEqual(out['decision'],'DENY')
        self.assertEqual(out['reason'],'HUMAN_APPROVAL_REQUIRED')

    def test_high_impact_requires_human_approval(self):
        out=authorize_connector_call(CONNECTOR,{'operation':'write','resource':'workspace/demo/file.txt'},GRANT)
        self.assertEqual(out['reason'],'HUMAN_APPROVAL_REQUIRED')

    def test_approved_high_impact_can_proceed_within_scope(self):
        out=authorize_connector_call(CONNECTOR,{'operation':'write','resource':'workspace/demo/file.txt','human_approval':True},GRANT)
        self.assertEqual(out['decision'],'ALLOW')

    def test_ambient_credentials_connector_denied(self):
        bad={**CONNECTOR,'ambient_credentials':True}
        out=authorize_connector_call(bad,{'operation':'read','resource':'workspace/demo/file.txt'},GRANT)
        self.assertEqual(out['reason'],'AMBIENT_CREDENTIALS_FORBIDDEN')


if __name__=='__main__':
    unittest.main()
