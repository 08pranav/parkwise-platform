import 'package:core/core.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:owner_app/features/slots/widgets/slot_card.dart';

SlotModel slot({
  String approval = 'approved',
  bool active = true,
  String notes = '',
}) => SlotModel(
  id: 'k1',
  society: 'soc-1',
  slotNumber: 'B-12',
  floor: '2',
  slotType: 'bike',
  state: 'available',
  ownershipType: 'resident',
  hourlyRate: '25.00',
  approvalStatus: approval,
  approvalNotes: notes,
  isActive: active,
  availableFrom: '09:00:00',
  availableTo: '18:00:00',
  createdAt: '2026-06-01T10:00:00Z',
);

Future<void> pump(
  WidgetTester tester,
  SlotModel s,
  ValueChanged<bool> onToggle,
) => tester.pumpWidget(
  MaterialApp(
    home: Scaffold(
      body: SlotCard(slot: s, onToggle: onToggle),
    ),
  ),
);

void main() {
  testWidgets('shows slot details and the approval state', (tester) async {
    await pump(tester, slot(), (_) {});
    expect(find.text('Slot B-12 · Floor 2'), findsOneWidget);
    expect(find.textContaining('₹25.00/hour · 09:00–18:00'), findsOneWidget);
    expect(find.text('Approved'), findsOneWidget);
  });

  testWidgets('an approved slot can be switched off', (tester) async {
    bool? changed;
    await pump(tester, slot(), (v) => changed = v);
    await tester.tap(find.byType(Switch));
    expect(changed, isFalse);
  });

  testWidgets('a pending slot cannot be toggled until approved', (
    tester,
  ) async {
    bool? changed;
    await pump(tester, slot(approval: 'pending'), (v) => changed = v);
    expect(find.text('Awaiting approval'), findsOneWidget);
    expect(tester.widget<Switch>(find.byType(Switch)).value, isFalse);
    expect(
      find.text('Available once your society admin approves'),
      findsOneWidget,
    );
    await tester.tap(find.byType(Switch), warnIfMissed: false);
    expect(changed, isNull);
  });

  testWidgets('shows the admin note on a rejected slot', (tester) async {
    await pump(
      tester,
      slot(approval: 'rejected', notes: 'Slot is on the fire lane'),
      (_) {},
    );
    expect(find.text('Rejected'), findsOneWidget);
    expect(find.text('Slot is on the fire lane'), findsOneWidget);
  });
}
