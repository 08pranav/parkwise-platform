import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:guard_app/widgets/manual_code_dialog.dart';

Future<String?> openDialog(
  WidgetTester tester,
  void Function(String?) onResult,
) async {
  await tester.pumpWidget(
    MaterialApp(
      home: Builder(
        builder: (context) => Scaffold(
          body: Center(
            child: ElevatedButton(
              onPressed: () async =>
                  onResult(await showManualCodeDialog(context)),
              child: const Text('open'),
            ),
          ),
        ),
      ),
    ),
  );
  await tester.tap(find.text('open'));
  await tester.pumpAndSettle();
  return null;
}

void main() {
  testWidgets('returns the trimmed code the guard typed', (tester) async {
    String? result;
    var called = false;
    await openDialog(tester, (v) {
      result = v;
      called = true;
    });
    await tester.enterText(find.byType(TextFormField), '  abc.def.ghi  ');
    await tester.tap(find.text('Validate'));
    await tester.pumpAndSettle();
    expect(called, isTrue);
    expect(result, 'abc.def.ghi');
  });

  testWidgets('an empty code is rejected and the dialog stays open', (
    tester,
  ) async {
    var called = false;
    await openDialog(tester, (_) => called = true);
    await tester.tap(find.text('Validate'));
    await tester.pump();
    expect(find.text('Enter the code'), findsOneWidget);
    expect(called, isFalse);
  });

  testWidgets('cancelling returns null', (tester) async {
    String? result = 'unset';
    await openDialog(tester, (v) => result = v);
    await tester.tap(find.text('Cancel'));
    await tester.pumpAndSettle();
    expect(result, isNull);
  });
}
