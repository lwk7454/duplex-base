import 'dart:math' as math;
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../providers/session_provider.dart';
import 'waveform_painter.dart';

class HomeScreen extends ConsumerStatefulWidget {
  const HomeScreen({super.key});

  @override
  ConsumerState<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends ConsumerState<HomeScreen> {
  String _selectedMode = 'free_chat';
  final List<double> _waveformAmplitudes = List.generate(50, (i) => 0.0);

  final Map<String, String> _modeLabels = {
    'free_chat': 'Free Chat',
    'interview': 'Mock Interview',
    'travel': 'Travel Survival',
    'debate': 'Discussion & Debate',
  };

  // Simulate audio waveform animation
  void _animateWaveform() {
    Future.doWhile(() async {
      final sessionState = ref.read(sessionStateProvider);
      if (sessionState is! SessionConnected) return false;

      // Shift values left
      for (int i = 0; i < _waveformAmplitudes.length - 1; i++) {
        _waveformAmplitudes[i] = _waveformAmplitudes[i + 1];
      }
      // Add new random value at the end
      _waveformAmplitudes[_waveformAmplitudes.length - 1] =
          (sessionState is SessionConnected) ? (math.Random().nextDouble() * 0.8 - 0.4).abs() : 0.0;

      if (mounted) setState(() {});
      await Future.delayed(const Duration(milliseconds: 50));
      return mounted;
    });
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final sessionState = ref.watch(sessionStateProvider);
    if (sessionState is SessionConnected) {
      _animateWaveform();
    }
  }

  @override
  Widget build(BuildContext context) {
    final sessionState = ref.watch(sessionStateProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('English Tutor'),
        backgroundColor: Theme.of(context).colorScheme.inversePrimary,
      ),
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(24.0),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              // Status indicator
              _buildStatusCard(sessionState),
              const SizedBox(height: 32),

              // Waveform visualization when connected
              if (sessionState is SessionConnected) ...[
                Container(
                  height: 120,
                  decoration: BoxDecoration(
                    color: Theme.of(context).colorScheme.surfaceVariant,
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: WaveformWidget(
                    amplitudes: _waveformAmplitudes,
                  ),
                ),
                const SizedBox(height: 24),
              ],

              // Mode selector
              _buildModeSelector(sessionState),
              const SizedBox(height: 24),

              // Action buttons
              _buildActionButtons(sessionState),

              const Spacer(),

              // Info text
              _buildInfoText(),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildStatusCard(SessionState state) {
    Color statusColor;
    String statusText;
    IconData statusIcon;

    switch (state) {
      case SessionInitial():
        statusColor = Colors.grey;
        statusText = 'Not Connected';
        statusIcon = Icons.cloud_off;
      case SessionLoading():
        statusColor = Colors.orange;
        statusText = 'Connecting...';
        statusIcon = Icons.sync;
      case SessionConnected():
        statusColor = Colors.green;
        statusText = 'Connected to Tutor';
        statusIcon = Icons.cloud_done;
      case SessionError():
        statusColor = Colors.red;
        statusText = 'Connection Error';
        statusIcon = Icons.error;
    }

    return Card(
      elevation: 4,
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Row(
          children: [
            Icon(statusIcon, color: statusColor, size: 32),
            const SizedBox(width: 16),
            Text(
              statusText,
              style: Theme.of(context).textTheme.titleLarge?.copyWith(
                    color: statusColor,
                  ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildModeSelector(SessionState state) {
    final isLoading = state is SessionLoading || state is SessionConnected;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          'Practice Mode',
          style: Theme.of(context).textTheme.titleMedium,
        ),
        const SizedBox(height: 12),
        ..._modeLabels.entries.map((entry) {
          final mode = entry.key;
          final label = entry.value;
          return RadioListTile<String>(
            title: Text(label),
            value: mode,
            groupValue: _selectedMode,
            onChanged: isLoading ? null : (v) => setState(() => _selectedMode = v!),
          );
        }),
      ],
    );
  }

  Widget _buildActionButtons(SessionState state) {
    final isLoading = state is SessionLoading;
    final isConnected = state is SessionConnected;

    return Column(
      children: [
        SizedBox(
          height: 56,
          child: FilledButton(
            onPressed: isLoading
                ? null
                : isConnected
                    ? null
                    : () => ref.read(sessionStateProvider.notifier).createSession(_selectedMode),
            child: isLoading
                ? const SizedBox(
                    width: 24,
                    height: 24,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : Text(isConnected ? 'Session Active' : 'Start Session'),
          ),
        ),
        if (isConnected) ...[
          const SizedBox(height: 12),
          SizedBox(
            height: 56,
            child: OutlinedButton(
              onPressed: () => ref.read(sessionStateProvider.notifier).stopSession(),
              child: const Text('End Session'),
            ),
          ),
        ],
        if (state is SessionError) ...[
          const SizedBox(height: 12),
          Text(
            (state as SessionError).message,
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
                  color: Theme.of(context).colorScheme.error,
                ),
            textAlign: TextAlign.center,
          ),
        ],
      ],
    );
  }

  Widget _buildInfoText() {
    return Text(
      'Speak clearly to practice English conversation.\n'
      'Your tutor will respond naturally and help improve your fluency.',
      style: Theme.of(context).textTheme.bodySmall?.copyWith(
            color: Colors.grey[600],
          ),
      textAlign: TextAlign.center,
    );
  }
}
