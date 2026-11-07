import 'package:core/core.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:get_it/get_it.dart';
import 'package:go_router/go_router.dart';

import '../data/slots_repository.dart';

class SlotFormScreen extends StatefulWidget {
  const SlotFormScreen({super.key});

  @override
  State<SlotFormScreen> createState() => _SlotFormScreenState();
}

class _SlotFormScreenState extends State<SlotFormScreen> {
  final _formKey = GlobalKey<FormState>();
  final _number = TextEditingController();
  final _floor = TextEditingController();
  final _rate = TextEditingController(text: '30');
  String _type = 'car';
  TimeOfDay _from = const TimeOfDay(hour: 9, minute: 0);
  TimeOfDay _to = const TimeOfDay(hour: 18, minute: 0);
  bool _saving = false;

  @override
  void dispose() {
    _number.dispose();
    _floor.dispose();
    _rate.dispose();
    super.dispose();
  }

  String _fmt(TimeOfDay t) =>
      '${t.hour.toString().padLeft(2, '0')}:${t.minute.toString().padLeft(2, '0')}:00';

  Future<void> _pick(bool isFrom) async {
    final picked = await showTimePicker(
      context: context,
      initialTime: isFrom ? _from : _to,
    );
    if (picked != null) setState(() => isFrom ? _from = picked : _to = picked);
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    if (_to.hour * 60 + _to.minute <= _from.hour * 60 + _from.minute) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('End time must be after start time')),
      );
      return;
    }
    final authState = context.read<AuthBloc>().state;
    if (authState is! Authenticated || authState.user.society == null) return;
    setState(() => _saving = true);
    try {
      await SlotsRepository(GetIt.I<ApiClient>()).create(
        societyId: authState.user.society!,
        slotNumber: _number.text.trim(),
        floor: _floor.text.trim(),
        slotType: _type,
        hourlyRate: _rate.text.trim(),
        availableFrom: _fmt(_from),
        availableTo: _fmt(_to),
      );
      if (mounted) context.pop();
    } catch (_) {
      if (mounted) {
        setState(() => _saving = false);
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text(
              'Could not save the slot. Check the details and try again.',
            ),
          ),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Add a parking slot')),
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 420),
              child: Form(
                key: _formKey,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    AppTextField(
                      controller: _number,
                      label: 'SLOT NUMBER',
                      hint: 'e.g. B-12',
                      prefixIcon: Icons.tag,
                      validator: (v) => (v == null || v.trim().isEmpty)
                          ? 'Slot number is required'
                          : null,
                    ),
                    const SizedBox(height: 14),
                    AppTextField(
                      controller: _floor,
                      label: 'FLOOR (OPTIONAL)',
                      hint: 'e.g. 1',
                      prefixIcon: Icons.layers_outlined,
                    ),
                    const SizedBox(height: 14),
                    SegmentedButton<String>(
                      segments: const [
                        ButtonSegment(
                          value: 'car',
                          label: Text('Car'),
                          icon: Icon(Icons.directions_car_rounded),
                        ),
                        ButtonSegment(
                          value: 'bike',
                          label: Text('Bike'),
                          icon: Icon(Icons.two_wheeler_rounded),
                        ),
                      ],
                      selected: {_type},
                      onSelectionChanged: (s) =>
                          setState(() => _type = s.first),
                    ),
                    const SizedBox(height: 14),
                    AppTextField(
                      controller: _rate,
                      label: 'BASE RATE (₹ PER HOUR)',
                      hint: '30',
                      keyboardType: TextInputType.number,
                      prefixIcon: Icons.currency_rupee,
                      validator: (v) {
                        final n = double.tryParse(v ?? '');
                        return (n == null || n <= 0)
                            ? 'Enter a rate above 0'
                            : null;
                      },
                    ),
                    const SizedBox(height: 14),
                    Row(
                      children: [
                        Expanded(
                          child: OutlinedButton.icon(
                            onPressed: () => _pick(true),
                            icon: const Icon(Icons.schedule),
                            label: Text('From ${_from.format(context)}'),
                          ),
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: OutlinedButton.icon(
                            onPressed: () => _pick(false),
                            icon: const Icon(Icons.schedule),
                            label: Text('To ${_to.format(context)}'),
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 28),
                    PrimaryButton(
                      label: 'SUBMIT FOR APPROVAL',
                      isLoading: _saving,
                      onPressed: _submit,
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
