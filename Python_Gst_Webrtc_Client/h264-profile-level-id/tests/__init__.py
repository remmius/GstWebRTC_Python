import unittest

from h264_profile_level_id import *


class TestMethods(unittest.TestCase):
    def test_parsing_invalid(self):
        # Malformed strings.
        self.assertIsNone(parseProfileLevelId())
        self.assertIsNone(parseProfileLevelId(''))
        self.assertIsNone(parseProfileLevelId(' 42e01f'))
        self.assertIsNone(parseProfileLevelId('4242e01f'))
        self.assertIsNone(parseProfileLevelId('e01f'))
        self.assertIsNone(parseProfileLevelId('gggggg'))

        # Invalid level.
        self.assertIsNone(parseProfileLevelId('42e000'))
        self.assertIsNone(parseProfileLevelId('42e00f'))
        self.assertIsNone(parseProfileLevelId('42e0ff'))

        # Invalid profile.
        self.assertIsNone(parseProfileLevelId('42e11f'))
        self.assertIsNone(parseProfileLevelId('58601f'))
        self.assertIsNone(parseProfileLevelId('64e01f'))

    def test_parsing_level(self):
        self.assertEqual(parseProfileLevelId('42e01f').level, Level3_1)
        self.assertEqual(parseProfileLevelId('42e00b').level, Level1_1)
        self.assertEqual(parseProfileLevelId('42f00b').level, Level1_b)
        self.assertEqual(parseProfileLevelId('42C02A').level, Level4_2)
        self.assertEqual(parseProfileLevelId('640c34').level, Level5_2)
    
    def test_parsing_constrained_baseline(self):
        self.assertEqual(parseProfileLevelId('42e01f').profile, ProfileConstrainedBaseline)
        self.assertEqual(parseProfileLevelId('42C02A').profile, ProfileConstrainedBaseline)
        self.assertEqual(parseProfileLevelId('4de01f').profile, ProfileConstrainedBaseline)
        self.assertEqual(parseProfileLevelId('58f01f').profile, ProfileConstrainedBaseline)

    def test_parsing_baseline(self):
        self.assertEqual(parseProfileLevelId('42a01f').profile, ProfileBaseline)
        self.assertEqual(parseProfileLevelId('58A01F').profile, ProfileBaseline)
    
    def test_parsing_main(self):
        self.assertEqual(parseProfileLevelId('4D401f').profile, ProfileMain)
    
    def test_parsing_high(self):
        self.assertEqual(parseProfileLevelId('64001f').profile, ProfileHigh)
    
    def test_parsing_constrained_high(self):
        self.assertEqual(parseProfileLevelId('640c1f').profile, ProfileConstrainedHigh)
    
    def test_to_string(self):
        self.assertEqual(profileLevelIdToString(ProfileLevelId(ProfileConstrainedBaseline, Level3_1)), '42e01f')
        self.assertEqual(profileLevelIdToString(ProfileLevelId(ProfileBaseline, Level1)), '42000a')
        self.assertEqual(profileLevelIdToString(ProfileLevelId(ProfileMain, Level3_1)), '4d001f')
        self.assertEqual(profileLevelIdToString(ProfileLevelId(ProfileConstrainedHigh, Level4_2)), '640c2a')
        self.assertEqual(profileLevelIdToString(ProfileLevelId(ProfileHigh, Level4_2)), '64002a')
    
    def test_to_string_level1b(self):
        self.assertEqual(profileLevelIdToString(ProfileLevelId(ProfileConstrainedBaseline, Level1_b)), '42f00b')
        self.assertEqual(profileLevelIdToString(ProfileLevelId(ProfileBaseline, Level1_b)), '42100b')
        self.assertEqual(profileLevelIdToString(ProfileLevelId(ProfileMain, Level1_b)), '4d100b')
    
    def test_to_string_from_string(self):
        self.assertEqual(profileLevelIdToString(parseProfileLevelId('42e01f')), '42e01f')
        self.assertEqual(profileLevelIdToString(parseProfileLevelId('42E01F')), '42e01f')
        self.assertEqual(profileLevelIdToString(parseProfileLevelId('4d100b')), '4d100b')
        self.assertEqual(profileLevelIdToString(parseProfileLevelId('4D100B')), '4d100b')
        self.assertEqual(profileLevelIdToString(parseProfileLevelId('640c2a')), '640c2a')
        self.assertEqual(profileLevelIdToString(parseProfileLevelId('640C2A')), '640c2a')
    
    def test_to_string_invalid(self):
        self.assertIsNone(profileLevelIdToString(ProfileLevelId(ProfileHigh, Level1_b)))
        self.assertIsNone(profileLevelIdToString(ProfileLevelId(ProfileConstrainedHigh, Level1_b)))
        self.assertIsNone(profileLevelIdToString(ProfileLevelId(255, Level3_1)))
    
    def test_parse_sdp_profile_level_id_enmpy(self):
        self.assertEqual(parseSdpProfileLevelId().profile, ProfileConstrainedBaseline)
        self.assertEqual(parseSdpProfileLevelId().level, Level3_1)
    
    def test_parse_sdp_profile_level_id_constrained_high(self):
        params = { 'profile-level-id': '640c2a' }
        self.assertEqual(parseSdpProfileLevelId(params).profile, ProfileConstrainedHigh)
        self.assertEqual(parseSdpProfileLevelId(params).level, Level4_2)
    
    def test_parse_sdp_profile_level_id_invalid(self):
        params = { 'profile-level-id': 'foobar' }
        self.assertIsNone(parseSdpProfileLevelId(params))
    
    def test_is_same_profile(self):
        self.assertTrue(isSameProfile({ 'foo': 'foo' }, { 'bar': 'bar' }))
        self.assertTrue(isSameProfile({ 'profile-level-id': '42e01f' }, { 'profile-level-id': '42C02A' }))
        self.assertTrue(isSameProfile({ 'profile-level-id': '42a01f' }, { 'profile-level-id': '58A01F' }))
        self.assertTrue(isSameProfile({ 'profile-level-id': '42e01f' }))
    
    def test_is_noe_same_profile(self):
        self.assertFalse(isSameProfile({}, { 'profile-level-id': '4d001f' }))
        self.assertFalse(isSameProfile({ 'profile-level-id': '42a01f' }, { 'profile-level-id': '640c1f' }))
        self.assertFalse(isSameProfile({ 'profile-level-id': '42000a' }, { 'profile-level-id': '64002a' }))
    
    def test_generate_profile_level_id_for_answer_empty(self):
        self.assertIsNone(generateProfileLevelIdForAnswer())
    
    def test_generate_profile_level_id_for_answer_level_symmetry_capped(self):
        low_level = {'profile-level-id' : '42e015'}
        high_level = {'profile-level-id' : '42e01f'}
        self.assertEqual(generateProfileLevelIdForAnswer(low_level, high_level), '42e015')
        self.assertEqual(generateProfileLevelIdForAnswer(high_level, low_level), '42e015')
    
    def test_generate_profile_level_id_for_answer_constrained_baseline_level_asymmetry(self):
        local_params = {
            'profile-level-id'        : '42e01f',
            'level-asymmetry-allowed' : '1'
        }
        remote_params = {
            'profile-level-id'        : '42e015',
            'level-asymmetry-allowed' : '1'
        }
        self.assertEqual(generateProfileLevelIdForAnswer(local_params, remote_params), '42e01f')

if __name__ == '__main__':
    unittest.main()