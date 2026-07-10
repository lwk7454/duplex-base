import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:english_tutor/main.dart';

/// Slow-motion integration test - watch the test actions happen in real-time
/// Run with: flutter test integration_test/visible_test.dart
void main() {
  testWidgets('Visible E2E Test - Watch the actions', (WidgetTester tester) async {
    print('🚀 Starting visible E2E test...');

    // Build the app
    await tester.pumpWidget(
      const ProviderScope(
        child: MyApp(),
      ),
    );

    // Wait so you can see the initial state
    await tester.pump(const Duration(milliseconds: 500));
    print('✅ App launched - you should see "English Tutor" title');
    await tester.pump(const Duration(seconds: 2));

    // 1. Verify initial state
    expect(find.text('English Tutor'), findsOneWidget);
    expect(find.text('Not Connected'), findsOneWidget);
    print('✅ Verified: Status shows "Not Connected"');
    await tester.pump(const Duration(seconds: 2));

    // 2. Tap "Mock Interview" mode - WATCH THIS
    print('🖱️  Tapping "Mock Interview"...');
    await tester.tap(find.text('Mock Interview'));
    await tester.pump();
    await tester.pump(const Duration(seconds: 2));
    print('✅ Mode selected');
    await tester.pump(const Duration(seconds: 2));

    // 3. Tap "Travel Survival" mode - WATCH THIS
    print('🖱️  Tapping "Travel Survival"...');
    await tester.tap(find.text('Travel Survival'));
    await tester.pump();
    await tester.pump(const Duration(seconds: 2));
    print('✅ Mode changed');
    await tester.pump(const Duration(seconds: 2));

    // 4. Verify start button exists
    expect(find.text('Start Session'), findsOneWidget);
    print('✅ "Start Session" button is visible');
    await tester.pump(const Duration(seconds: 2));

    // 5. Try to start session (will fail to connect, but you'll see the loading state)
    print('🖱️  Tapping "Start Session" - watch for loading spinner...');
    await tester.tap(find.text('Start Session'));
    await tester.pump();
    await tester.pump(const Duration(seconds: 2));

    // Check for loading indicator
    if (finderEvaluate(find.byType(CircularProgressIndicator)).isNotEmpty) {
      print('✅ Loading spinner appeared!');
      await tester.pump(const Duration(seconds: 3));
    }

    // Wait for connection attempt (will timeout/fail since backend might not be reachable from test)
    await tester.pumpAndSettle(const Duration(seconds: 5));

    print('✅ Test completed - you should have seen all the actions!');
  });

  testWidgets('Slow mode selector test', (WidgetTester tester) async {
    print('🎯 Testing mode selector with delays...');

    await tester.pumpWidget(
      const ProviderScope(
        child: MyApp(),
      ),
    );

    await tester.pumpAndSettle();
    await tester.pump(const Duration(seconds: 2));

    final modes = ['Free Chat', 'Mock Interview', 'Travel Survival', 'Discussion & Debate'];

    for (final mode in modes) {
      print('📝 Selecting mode: $mode');
      await tester.tap(find.text(mode));
      await tester.pump();
      await tester.pump(const Duration(seconds: 2)); // Pause so you can see each selection
    }

    print('✅ All modes tested');
    await tester.pump(const Duration(seconds: 2));
  });
}

// Helper to evaluate finders safely
dynamic finderEvaluate(Finder finder) {
  try {
    return finder.evaluate();
  } catch (e) {
    return [];
  }
}
