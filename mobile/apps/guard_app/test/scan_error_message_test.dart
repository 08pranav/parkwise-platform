import 'package:core/core.dart';
import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:guard_app/cubits/scan_cubit.dart';

void main() {
  test('shows the server message when Dio wraps an ApiException', () {
    final wrapped = DioException(
      requestOptions: RequestOptions(path: '/qr/entry/'),
      error: const ApiException(
        message: 'This booking does not belong to your society.',
        statusCode: 400,
      ),
    );
    expect(
      scanErrorMessage(wrapped),
      'This booking does not belong to your society.',
    );
  });

  test('shows a plain ApiException message as it is', () {
    expect(scanErrorMessage(const ApiException(message: 'Expired')), 'Expired');
  });

  test('hides raw exception text for anything unexpected', () {
    expect(scanErrorMessage(StateError('boom')), isNot(contains('boom')));
  });
}
