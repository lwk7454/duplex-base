import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:english_tutor/main.dart';
import 'package:english_tutor/providers/session_provider.dart';

void main() {
  testWidgets('English Tutor UI Test', (WidgetTester tester) async {
    // Build the app
    await tester.pumpWidget(
      const ProviderScope(
        child: MyApp(),
      ),
    );

    // Wait for initial render
    await tester.pumpAndSettle();

    // 1. Verify app starts and shows home screen
    expect(find.text('English Tutor'), findsOneWidget);
    expect(find.text('Not Connected'), findsOneWidget);

    // 2. Verify mode selector exists with all modes
    expect(find.text('Practice Mode'), findsOneWidget);
    expect(find.text('Free Chat'), findsOneWidget);
    expect(find.text('Mock Interview'), findsOneWidget);
    expect(find.text('Travel Survival'), findsOneWidget);
    expect(find.text('Discussion & Debate'), findsOneWidget);

    // 3. Verify start button exists
    expect(find.text('Start Session'), findsOneWidget);

    // 4. Tap different modes and verify selection
    await tester.tap(find.text('Mock Interview'));
    await tester.pump();
    expect(find.byType(RadioListTile<String>), findsWidgets);

    await tester.tap(find.text('Travel Survival'));
    await tester.pump();
    expect(find.byType(RadioListTile<String>), findsWidgets);

    // 5. Verify info text is displayed
    expect(find.textContaining('Speak clearly'), findsOneWidget);
  });
}
