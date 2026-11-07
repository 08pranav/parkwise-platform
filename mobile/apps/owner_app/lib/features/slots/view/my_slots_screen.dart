import 'package:core/core.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:get_it/get_it.dart';
import 'package:go_router/go_router.dart';

import '../cubit/slots_cubit.dart';
import '../data/slots_repository.dart';
import '../widgets/slot_card.dart';

class MySlotsScreen extends StatelessWidget {
  const MySlotsScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final authState = context.watch<AuthBloc>().state;
    if (authState is! Authenticated) return const SizedBox.shrink();
    return BlocProvider(
      create: (_) => SlotsCubit(
        SlotsRepository(GetIt.I<ApiClient>()),
        user: authState.user,
      )..load(),
      child: _MySlotsView(userName: authState.user.fullName),
    );
  }
}

class _MySlotsView extends StatelessWidget {
  const _MySlotsView({required this.userName});

  final String userName;

  @override
  Widget build(BuildContext context) {
    final cubit = context.read<SlotsCubit>();
    return Scaffold(
      appBar: AppBar(
        title: const Text('My parking slots'),
        actions: [
          IconButton(
            tooltip: 'Notifications',
            icon: const Icon(Icons.notifications_outlined),
            onPressed: () => context.push('/notifications'),
          ),
          IconButton(
            tooltip: 'Sign out',
            icon: const Icon(Icons.logout_rounded),
            onPressed: () =>
                context.read<AuthBloc>().add(const AuthLoggedOut()),
          ),
        ],
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () async {
          await context.push('/slots/new');
          cubit.load();
        },
        icon: const Icon(Icons.add),
        label: const Text('Add slot'),
      ),
      body: BlocBuilder<SlotsCubit, SlotsState>(
        builder: (context, state) => switch (state) {
          SlotsLoading() => const LoadingWidget(),
          SlotsFailure(:final message) =>
            AppErrorWidget(message: message, onRetry: cubit.load),
          SlotsLoaded(:final slots) => RefreshIndicator(
              onRefresh: cubit.load,
              child: slots.isEmpty
                  ? ListView(children: const [
                      SizedBox(height: 120),
                      EmptyStateWidget(
                        icon: Icons.local_parking_rounded,
                        title: 'No slots listed yet',
                        subtitle:
                            'Add your spare slot. Your society admin approves it before visitors can book.',
                      ),
                    ])
                  : ListView.separated(
                      padding: const EdgeInsets.fromLTRB(16, 16, 16, 96),
                      itemCount: slots.length,
                      separatorBuilder: (_, _) => const SizedBox(height: 12),
                      itemBuilder: (context, i) => SlotCard(
                        slot: slots[i],
                        onToggle: (value) async {
                          final error = await cubit.setActive(slots[i], value);
                          if (error != null && context.mounted) {
                            ScaffoldMessenger.of(context)
                                .showSnackBar(SnackBar(content: Text(error)));
                          }
                        },
                      ),
                    ),
            ),
        },
      ),
    );
  }
}
