import 'package:core/core.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('ApiEndpoints', () {
    test('auth endpoints', () {
      expect(ApiEndpoints.login, '/api/v1/auth/login/');
      expect(ApiEndpoints.profile, '/api/v1/auth/profile/');
    });

    test('slot endpoints are built from ids', () {
      expect(
        ApiEndpoints.slotToggleActive('s1', 'k1'),
        '/api/v1/societies/s1/slots/k1/toggle-active/',
      );
      expect(
        ApiEndpoints.notificationRead('n1'),
        '/api/v1/auth/notifications/n1/read/',
      );
    });
  });

  group('EnvConfig', () {
    test('falls back to the local dev server without API_BASE_URL', () {
      expect(EnvConfig.current.apiBaseUrl, startsWith('http://'));
      expect(EnvConfig.current.apiBaseUrl, isNot(endsWith('/')));
    });

    test('demo mode is off unless explicitly enabled', () {
      expect(EnvConfig.demoMode, isFalse);
    });
  });

  group('SlotModel', () {
    final json = <String, dynamic>{
      'id': 'slot-1',
      'society': 'soc-1',
      'slot_number': 'B-12',
      'floor': '1',
      'slot_type': 'car',
      'state': 'available',
      'ownership_type': 'resident',
      'owner': 'user-1',
      'owner_name': 'Asha',
      'approval_status': 'pending',
      'approval_notes': '',
      'hourly_rate': '30.00',
      'is_active': true,
      'created_at': '2026-06-01T10:00:00Z',
      'available_from': '09:00:00',
      'available_to': '18:00:00',
    };

    test('parses the API payload', () {
      final slot = SlotModel.fromJson(json);
      expect(slot.slotNumber, 'B-12');
      expect(slot.hourlyRate, '30.00');
      expect(slot.isPendingApproval, isTrue);
      expect(slot.isAvailable, isTrue);
      expect(slot.isBlocked, isFalse);
    });

    test('round-trips through JSON', () {
      final slot = SlotModel.fromJson(json);
      expect(SlotModel.fromJson(slot.toJson()).toJson(), slot.toJson());
    });

    test('defaults to approved when the server omits the field', () {
      final slot = SlotModel.fromJson({...json}..remove('approval_status'));
      expect(slot.approvalStatus, 'approved');
    });
  });

  group('DemoAccount', () {
    test('every role has a distinct demo email', () {
      final emails = {
        DemoAccount.resident.email,
        DemoAccount.owner.email,
        DemoAccount.societyAdmin.email,
        DemoAccount.guard.email,
        DemoAccount.superAdmin.email,
      };
      expect(emails.length, 5);
    });
  });
}
