import 'package:flutter/material.dart';

/// Asks the guard to type or paste a booking's QR code text, for when the camera
/// cannot read the code. Returns the trimmed text, or null if cancelled.
Future<String?> showManualCodeDialog(BuildContext context) {
  return showDialog<String>(
    context: context,
    builder: (_) => const _ManualCodeDialog(),
  );
}

class _ManualCodeDialog extends StatefulWidget {
  const _ManualCodeDialog();

  @override
  State<_ManualCodeDialog> createState() => _ManualCodeDialogState();
}

class _ManualCodeDialogState extends State<_ManualCodeDialog> {
  final _formKey = GlobalKey<FormState>();
  final _controller = TextEditingController();

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  void _submit() {
    if (_formKey.currentState!.validate()) {
      Navigator.of(context).pop(_controller.text.trim());
    }
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Enter code manually'),
      content: Form(
        key: _formKey,
        child: TextFormField(
          controller: _controller,
          autofocus: true,
          minLines: 1,
          maxLines: 4,
          decoration: const InputDecoration(
            labelText: 'QR code text',
            hintText: 'Paste the code shown on the resident\'s phone',
          ),
          validator: (value) =>
              (value == null || value.trim().isEmpty) ? 'Enter the code' : null,
          onFieldSubmitted: (_) => _submit(),
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(),
          child: const Text('Cancel'),
        ),
        FilledButton(onPressed: _submit, child: const Text('Validate')),
      ],
    );
  }
}
