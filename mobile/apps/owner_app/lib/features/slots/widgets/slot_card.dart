import 'package:core/core.dart';
import 'package:flutter/material.dart';

class SlotCard extends StatelessWidget {
  const SlotCard({super.key, required this.slot, required this.onToggle});

  final SlotModel slot;
  final ValueChanged<bool> onToggle;

  ({String label, Color color}) _approval(ColorScheme scheme) {
    switch (slot.approvalStatus) {
      case 'approved':
        return (label: 'Approved', color: Colors.green);
      case 'rejected':
        return (label: 'Rejected', color: scheme.error);
      default:
        return (label: 'Awaiting approval', color: Colors.orange);
    }
  }

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final approval = _approval(scheme);
    final approved = slot.approvalStatus == 'approved';
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(
                  slot.slotType == 'bike'
                      ? Icons.two_wheeler_rounded
                      : Icons.directions_car_rounded,
                  color: scheme.primary,
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: Text(
                    'Slot ${slot.slotNumber}'
                    '${slot.floor.isEmpty ? '' : ' · Floor ${slot.floor}'}',
                    style: Theme.of(context).textTheme.titleMedium,
                  ),
                ),
                Chip(
                  label: Text(approval.label),
                  side: BorderSide(color: approval.color),
                  labelStyle: TextStyle(color: approval.color, fontSize: 12),
                ),
              ],
            ),
            const SizedBox(height: 8),
            Text('₹${slot.hourlyRate}/hour'
                '${slot.availableFrom != null ? ' · ${slot.availableFrom}–${slot.availableTo}' : ''}'),
            if (slot.approvalNotes.isNotEmpty) ...[
              const SizedBox(height: 6),
              Text(slot.approvalNotes,
                  style: TextStyle(color: scheme.onSurfaceVariant)),
            ],
            const SizedBox(height: 8),
            SwitchListTile(
              contentPadding: EdgeInsets.zero,
              title: const Text('Open for bookings'),
              subtitle: approved
                  ? null
                  : const Text('Available once your society admin approves'),
              value: slot.isActive,
              onChanged: approved ? onToggle : null,
            ),
          ],
        ),
      ),
    );
  }
}
