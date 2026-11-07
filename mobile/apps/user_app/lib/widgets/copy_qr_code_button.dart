import 'package:core/core.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:get_it/get_it.dart';

/// Copies the booking's QR text to the clipboard, so a guard can type or paste it
/// when the camera cannot read the code.
class CopyQrCodeButton extends StatefulWidget {
  const CopyQrCodeButton({super.key, required this.bookingId});

  final String bookingId;

  @override
  State<CopyQrCodeButton> createState() => _CopyQrCodeButtonState();
}

class _CopyQrCodeButtonState extends State<CopyQrCodeButton> {
  bool _busy = false;

  Future<void> _copy() async {
    setState(() => _busy = true);
    String message;
    try {
      final response = await GetIt.I<ApiClient>().get<Map<String, dynamic>>(
        ApiEndpoints.bookingQrToken(widget.bookingId),
      );
      final token = response.data?['qr_token'] as String?;
      if (token == null || token.isEmpty) {
        message = 'The code is not available yet.';
      } else {
        await Clipboard.setData(ClipboardData(text: token));
        message =
            'Code copied. Give it to the guard if the camera cannot scan.';
      }
    } catch (_) {
      message =
          'Could not fetch the code. Check your connection and try again.';
    }
    if (!mounted) return;
    setState(() => _busy = false);
    ScaffoldMessenger.of(
      context,
    ).showSnackBar(SnackBar(content: Text(message)));
  }

  @override
  Widget build(BuildContext context) {
    return TextButton.icon(
      onPressed: _busy ? null : _copy,
      icon: _busy
          ? const SizedBox(
              width: 16,
              height: 16,
              child: CircularProgressIndicator(strokeWidth: 2),
            )
          : const Icon(Icons.copy_rounded, size: 18),
      label: const Text('Copy code for manual entry'),
    );
  }
}
