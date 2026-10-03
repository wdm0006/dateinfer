import os
import unittest
from datetime import datetime
import dateinfer
from dateinfer.date_elements import *
from dateinfer.infer import infer, _mode, _most_restrictive, _tag_most_likely, _percent_match, _tokenize_by_character_class
import dateinfer.ruleproc as ruleproc
import yaml

EXAMPLES_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'examples.yaml')

TIMEZONE_DEPENDENT = {
    # %Z accepts MST/EST only when they are local timezone names.
    'en_US.UTF-8',
    'Non-24 Hour en_US.UTF-8',
    'Non-24 Hour, no seconds en_US.UTF-8',
}
KNOWN_UNPARSEABLE = TIMEZONE_DEPENDENT | {
    # The example 13.2.8 has a one-digit year; %y requires two digits.
    'German (Traditional, Short) dd.mm.yy',
}


class TestCorpusRoundTrip(unittest.TestCase):
    def testExamplesParseWithInferredFormat(self):
        with open(EXAMPLES_PATH, 'r') as f:
            documents = list(yaml.safe_load_all(f))
        names = {document['name'] for document in documents}
        self.assertFalse(KNOWN_UNPARSEABLE - names, 'Unknown corpus exclusions')

        for document in documents:
            name = document['name']
            if name in TIMEZONE_DEPENDENT:
                continue
            with self.subTest(name=name):
                examples = document['examples']
                inferred = infer(examples)
                failures = []
                for example in examples:
                    try:
                        datetime.strptime(example, inferred)
                    except Exception as error:
                        failures.append('{0!r} under {1!r}: {2}: {3}'.format(
                            example, inferred, type(error).__name__, error))
                if name in KNOWN_UNPARSEABLE:
                    self.assertTrue(failures, 'Corpus now round-trips; remove its exclusion')
                else:
                    self.assertFalse(failures, '\n'.join(failures))


def load_tests(loader, standard_tests, ignored):
    """
    Return a TestSuite containing standard_tests plus generated test cases
    """
    suite = unittest.TestSuite()
    suite.addTests(standard_tests)

    with open(EXAMPLES_PATH, 'r') as f:
        examples = yaml.safe_load_all(f)
        for example in examples:
            suite.addTest(test_case_for_example(example))

    return suite


def test_case_for_example(test_data):
    """
    Return an instance of TestCase containing a test for a date-format example
    """

    # This class definition placed inside method to prevent discovery by test loader
    class TestExampleDate(unittest.TestCase):
        def testFormat(self):
            # verify initial conditions
            self.assertTrue(hasattr(self, 'test_data'), 'testdata field not set on test object')

            expected = self.test_data['format']
            actual = infer(self.test_data['examples'])

            self.assertEqual(expected,
                             actual,
                             '{0}: Inferred `{1}`!=`{2}`'.format(self.test_data['name'], actual, expected))

    test_case = TestExampleDate(methodName='testFormat')
    test_case.test_data = test_data
    return test_case


class TestAmbiguousDateCases(unittest.TestCase):
    """
    TestCase for tests which results are ambiguous but can be assumed to fall in a small set of possibilities.
    """
    def testAmbg1(self):
        self.assertIn(infer(['1/1/2012']), ['%m/%d/%Y', '%d/%m/%Y'])

    def testAmbg2(self):
        # Note: as described in Issue #5 (https://github.com/jeffreystarr/dateinfer/issues/5), the result
        # should be %d/%m/%Y as the more likely choice. However, at this point, we will allow %m/%d/%Y.
        self.assertIn(infer(['04/12/2012', '05/12/2012', '06/12/2012', '07/12/2012']),
                      ['%d/%m/%Y', '%m/%d/%Y'])


class TestAlternativeRules(unittest.TestCase):
    def testDefaultRulesAreUsedWhenAlternativeRulesAreOmitted(self):
        self.assertEqual('%m/%d/%y', infer(['12/12/12']))

    def testEmptyAlternativeRulesApplyNoRewrites(self):
        self.assertEqual('%m/%m/%m', infer(['12/12/12'], alt_rules=[]))

    def testAlternativeRulesReplaceDefaultRules(self):
        rules = [ruleproc.If(ruleproc.Contains(MonthNum), ruleproc.Swap(MonthNum, Year4))]

        self.assertEqual('%Y/%m/%m', infer(['12/12/12'], alt_rules=rules))


class TestEmptyExamples(unittest.TestCase):
    def testEmptyListRaisesValueError(self):
        with self.assertRaises(ValueError):
            dateinfer.infer([])

    def testEmptyStringExampleStillInfers(self):
        self.assertEqual('', dateinfer.infer(['']))


class TestTextualMonthRecognizers(unittest.TestCase):
    def testEmptyTokenDoesNotMatch(self):
        self.assertFalse(MonthTextShort.is_match(''))
        self.assertFalse(MonthTextLong.is_match(''))

    def testValidMonthNamesMatch(self):
        self.assertTrue(MonthTextShort.is_match('Jan'))
        self.assertTrue(MonthTextLong.is_match('January'))


class TestTrailingTimes(unittest.TestCase):
    def assertExamplesParseWithInferredFormat(self, examples, expected):
        inferred = infer(examples)
        self.assertEqual(expected, inferred)
        for example in examples:
            datetime.strptime(example, inferred)

    def test24HourTimeWithoutSeconds(self):
        self.assertExamplesParseWithInferredFormat(['12:21', '16:05'], '%H:%M')

    def test12HourTimeWithoutSeconds(self):
        self.assertExamplesParseWithInferredFormat(['1:21', '4:05'], '%I:%M')

    def testDateWithTrailingTimeWithoutSeconds(self):
        cases = [
            (['2014-01-11 12:21', '2015-02-16 16:05'], '%Y-%m-%d %H:%M'),
            (['2014-01-11T12:21', '2015-02-16T16:05'], '%Y-%m-%dT%H:%M'),
            (['12/31/1999 23:21', '01/02/2000 05:13'], '%m/%d/%Y %H:%M'),
        ]
        for examples, expected in cases:
            with self.subTest(expected=expected):
                self.assertExamplesParseWithInferredFormat(examples, expected)

    def testTimeWithSecondsRemainsSupported(self):
        self.assertExamplesParseWithInferredFormat(['12:21:05', '16:05:31'], '%H:%M:%S')


class TestUTCOffsets(unittest.TestCase):
    def assertExamplesParseWithInferredFormat(self, examples, expected):
        inferred = infer(examples)
        self.assertEqual(expected, inferred)
        for example in examples:
            datetime.strptime(example, inferred)

    def testColonDelimitedOffsetsParseWithInferredFormat(self):
        examples = ['2024-01-13T23:10:55+04:00', '2025-11-27T16:45:30-05:30']

        self.assertExamplesParseWithInferredFormat(examples, '%Y-%m-%dT%H:%M:%S%z')

    def testCompactOffsetsRemainSupported(self):
        examples = ['2014-01-11T12:21:05+0400', '2015-02-16T16:05:31-0400']

        self.assertExamplesParseWithInferredFormat(examples, '%Y-%m-%dT%H:%M:%S%z')

    def testCompactZeroOffsetsParseWithInferredFormat(self):
        cases = [
            (['2014-01-11T12:21:05+0000', '2015-02-16T16:05:31+0000'],
             '%Y-%m-%dT%H:%M:%S%z'),
            (['2014-01-11T12:21:05-0000', '2015-02-16T16:05:31-0000'],
             '%Y-%m-%dT%H:%M:%S%z'),
            (['Mon, 13 Jan 2014 09:52:52 +0000', 'Tue, 21 Jan 2014 15:30:00 +0000'],
             '%a, %d %b %Y %H:%M:%S %z'),
        ]

        for examples, expected in cases:
            with self.subTest(examples=examples):
                self.assertExamplesParseWithInferredFormat(examples, expected)


class TestTextualMonthDayOfMonth(unittest.TestCase):
    """
    TestCase for days of month in the 13..23 range, which are matched by Hour24 as well as DayOfMonth and
    so are tagged as an hour before the rewrite rules repair them.
    """
    def testMonthTextShortFirst(self):
        examples = ['Jan 13, 2014', 'Feb 21, 2013']
        inferred = infer(examples)

        self.assertEqual('%b %d, %Y', inferred)
        for example in examples:
            datetime.strptime(example, inferred)

    def testMonthTextLongFirst(self):
        examples = ['January 13, 2014', 'February 21, 2013']
        inferred = infer(examples)

        self.assertEqual('%B %d, %Y', inferred)
        for example in examples:
            datetime.strptime(example, inferred)

    def testDayFirst(self):
        examples = ['13 Jan 2014', '21 Feb 2013']
        inferred = infer(examples)

        self.assertEqual('%d %b %Y', inferred)
        for example in examples:
            datetime.strptime(example, inferred)

    def testDayLongMonthFirst(self):
        examples = ['13 January 2014', '21 February 2013']
        inferred = infer(examples)

        self.assertEqual('%d %B %Y', inferred)
        for example in examples:
            datetime.strptime(example, inferred)

    def testHourFollowingTextualMonthIsNotRewrittenAsDay(self):
        # the hour is not adjacent to the month, so it keeps %H (note: %Z with MST does not round-trip
        # through strptime, so only the format is asserted here)
        examples = ['Mon Jan 13 09:52:52 MST 2014', 'Tue Jan 21 15:30:00 EST 2014']

        self.assertEqual('%a %b %d %H:%M:%S %Z %Y', infer(examples))

    def testHourFollowingTextualMonthWithoutWeekday(self):
        examples = ['Jan 13 09:52:52 2014', 'Feb 21 15:30:00 2013']
        inferred = infer(examples)

        self.assertEqual('%b %d %H:%M:%S %Y', inferred)
        for example in examples:
            datetime.strptime(example, inferred)


class TestNotClause(unittest.TestCase):
    def testTrueWhenWrappedClauseIsFalse(self):
        self.assertTrue(ruleproc.Not(ruleproc.Contains(Minute)).is_true([Hour24(), Filler(':'), Second()]))

    def testFalseWhenWrappedClauseIsTrue(self):
        self.assertFalse(ruleproc.Not(ruleproc.Contains(Minute)).is_true([Hour24(), Filler(':'), Minute()]))


class TestTextualMonthYear2(unittest.TestCase):
    """
    A two-digit year <= 23 beside a textual month ties with Hour24 and DayOfMonth in the tagger.
    """
    def assertInfers(self, examples, expected):
        inferred = infer(examples)

        self.assertEqual(expected, inferred)
        for example in examples:
            datetime.strptime(example, inferred)

    def testMonthFirstShort(self):
        self.assertInfers(['Jan-11-14', 'Feb-16-15'], '%b-%d-%y')

    def testMonthFirstLong(self):
        self.assertInfers(['January-11-14', 'February-16-15'], '%B-%d-%y')

    def testDayFirstShort(self):
        self.assertInfers(['11 Jan 14', '16 Feb 15'], '%d %b %y')

    def testDayFirstLong(self):
        self.assertInfers(['11 January 14', '16 February 15'], '%d %B %y')

    def testHighYearsStillWork(self):
        self.assertInfers(['Jan-11-94', 'Feb-16-85'], '%b-%d-%y')

    def testRealTimeOfDayKeepsHour(self):
        # the Minute produced by the H:M:S rules keeps the guard off a genuine time slot
        self.assertEqual('%b %d %H:%M:%S', infer(['Jan 13 09:52:52', 'Feb 21 15:30:00']))


class TestYearFirstDates(unittest.TestCase):
    def testIsoDatetimeHourIsNotRewrittenAsDay(self):
        self.assertEqual('%Y-%m-%dT%I:%M:%S', infer(['2014-01-11T12:21:05']))


class TestCompactDates(unittest.TestCase):
    """
    TestCase for eight-digit year-first dates, which the tokenizer keeps as a single token and so are only
    recognized by CompactDate.
    """
    def testCompactDatesParseWithInferredFormat(self):
        examples = ['20130814', '20140102', '20151231']
        inferred = infer(examples)

        self.assertEqual('%Y%m%d', inferred)
        for example in examples:
            datetime.strptime(example, inferred)

    def testLeapDayIsRecognized(self):
        self.assertEqual('%Y%m%d', infer(['20120229', '20160229']))

    def testValidCompactDatesMatch(self):
        for token in ['20130814', '20140102', '20120229', '00010101', '99991231']:
            with self.subTest(token=token):
                self.assertTrue(CompactDate.is_match(token))

    def testImpossibleCompactDatesDoNotMatch(self):
        for token in ['20131340',  # month 13, day 40
                      '20130229',  # 2013 is not a leap year
                      '20130800',  # day 0
                      '20130000',  # month and day 0
                      '00000101']:  # year 0 is outside datetime's range
            with self.subTest(token=token):
                self.assertFalse(CompactDate.is_match(token))

    def testMalformedTokensDoNotMatch(self):
        for token in ['2013081',  # seven digits
                      '201308145',  # nine digits
                      '2013-08-14', '2013 814', '+2013081', 'Jan 2013', '']:
            with self.subTest(token=token):
                self.assertFalse(CompactDate.is_match(token))

    def testUnrecognizableEightDigitTokensAreNotTaggedAsDates(self):
        # a column of impossible dates is still filler-tagged rather than forced into %Y%m%d
        self.assertNotEqual('%Y%m%d', infer(['20131340', '20141302']))


class TestFractionalSeconds(unittest.TestCase):
    """
    TestCase for fractional seconds, where a digit run is a fraction of a second only by virtue of
    following a seconds field and a decimal point.
    """
    CORPUS_NAMES = ('ISO 8601 with milliseconds', 'ISO 8601 with microseconds')

    def assertExamplesParseWithInferredFormat(self, examples, expected):
        inferred = infer(examples)
        self.assertEqual(expected, inferred)
        for example in examples:
            datetime.strptime(example, inferred)

    def testMicrosecondsParseWithInferredFormat(self):
        examples = ['2013-08-14T10:30:00.123456', '2014-01-02T11:31:01.654321']

        self.assertExamplesParseWithInferredFormat(examples, '%Y-%m-%dT%I:%M:%S.%f')

    def testMillisecondsWithSpaceSeparatorParseWithInferredFormat(self):
        examples = ['2013-08-14 10:30:00.123', '2014-01-02 11:31:01.654']

        self.assertExamplesParseWithInferredFormat(examples, '%Y-%m-%d %I:%M:%S.%f')

    def testCorpusExamplesParseWithInferredFormat(self):
        with open(EXAMPLES_PATH, 'r') as f:
            documents = [d for d in yaml.safe_load_all(f) if d['name'] in self.CORPUS_NAMES]

        self.assertEqual(len(self.CORPUS_NAMES), len(documents))
        for document in documents:
            with self.subTest(name=document['name']):
                self.assertExamplesParseWithInferredFormat(document['examples'], document['format'])

    def testEveryFractionWidthIsRecognized(self):
        # %f accepts one to six digits; widths the tagger cannot claim are retagged by rule
        for fractions in [('5', '7'), ('12', '34'), ('123', '456'), ('1234', '5678'),
                          ('12345', '65432'), ('123456', '654321')]:
            examples = ['2013-08-14T10:30:00.{0}'.format(fractions[0]),
                        '2014-01-02T11:31:01.{0}'.format(fractions[1])]
            with self.subTest(fractions=fractions):
                self.assertExamplesParseWithInferredFormat(examples, '%Y-%m-%dT%I:%M:%S.%f')

    def testFractionFollowingTwentyFourHourTimeIsRecognized(self):
        examples = ['Mon Jan 13 09:52:52.250 2014', 'Tue Jan 21 15:30:00.500 2013']
        inferred = infer(examples)

        self.assertEqual('%a %b %d %H:%M:%S.%f %Y', inferred)
        for example in examples:
            datetime.strptime(example, inferred)

    def testDottedDateWithoutTimeIsUnaffected(self):
        # a dotted date has no seconds field, so its digit runs are not fractional seconds
        self.assertEqual('%d.%m.%y', infer(['31.12.91', '4.4.87', '13.2.8']))
        self.assertEqual('%d.%m.%Y', infer(['31.12.1991', '4.4.1987', '13.2.2008']))

    def testMicrosecondIsNumerical(self):
        self.assertTrue(Microsecond.is_numerical())

    def testUnclaimedDigitWidthsMatch(self):
        for token in ['123', '000', '999', '12345', '123456', '000001']:
            with self.subTest(token=token):
                self.assertTrue(Microsecond.is_match(token))

    def testWidthsClaimedByOtherElementsDoNotMatch(self):
        # a one-, two- or four-digit run is already tagged as a number by Minute, Year2 or Year4
        for token in ['1', '12', '1234', '1234567']:
            with self.subTest(token=token):
                self.assertFalse(Microsecond.is_match(token))

    def testNonDigitTokensDoNotMatch(self):
        for token in ['12a', '1.5', '+123', ' 123', '', '١٢٣', '１２３']:
            with self.subTest(token=token):
                self.assertFalse(Microsecond.is_match(token))


class TestMode(unittest.TestCase):
    def testUniqueMode(self):
        self.assertEqual(5, _mode([1, 3, 4, 5, 6, 5, 2, 5, 3]))

    def testEmptyListReturnsNone(self):
        self.assertIsNone(_mode([]))

    def testTiesReturnLeastValueRegardlessOfInputOrder(self):
        self.assertEqual(1, _mode([2, 2, 1, 1]))
        self.assertEqual(1, _mode([1, 1, 2, 2]))

    def testInferIsOrderIndependentWhenTokenLengthsTie(self):
        examples = ['12/31/1999 10:00:00', '11/11/1911']

        self.assertEqual(infer(examples), infer(list(reversed(examples))))


class TestMostRestrictive(unittest.TestCase):
    def testMostRestrictive(self):
        t = _most_restrictive

        self.assertEqual(MonthNum(), t([DayOfMonth(), MonthNum, Year4()]))
        self.assertEqual(Year2(), t([Year4(), Year2()]))


class TestPercentMatch(unittest.TestCase):
    def testPercentMatch(self):
        t = _percent_match
        patterns = (DayOfMonth, MonthNum, Filler)
        examples = ['1', '2', '24', 'b', 'c']

        percentages = t(patterns, examples)

        self.assertAlmostEqual(percentages[0], 0.6)  # DayOfMonth 1..31
        self.assertAlmostEqual(percentages[1], 0.4)  # Month 1..12
        self.assertAlmostEqual(percentages[2], 1.0)  # Filler any


class TestRuleElements(unittest.TestCase):
    def testDateElementHashMatchesEquality(self):
        first = MonthNum()
        second = MonthNum()

        self.assertEqual(first, second)
        self.assertIsInstance(hash(first), int)
        self.assertEqual(hash(first), hash(second))
        self.assertEqual(1, len({first, second}))
        self.assertEqual('month', {first: 'month'}[second])

    def testFind(self):
        elem_list = [Filler(' '), DayOfMonth(), Filler('/'), MonthNum(), Hour24(), Year4()]
        t = ruleproc.Sequence.find

        self.assertEqual(0, t([Filler(' ')], elem_list))
        self.assertEqual(3, t([MonthNum], elem_list))
        self.assertEqual(2, t([Filler('/'), MonthNum()], elem_list))
        self.assertEqual(4, t([Hour24, Year4()], elem_list))

        elem_list = [WeekdayShort, MonthTextShort, Filler(' '), Hour24, Filler(':'), Minute, Filler(':'), Second,
                     Filler(' '), Timezone, Filler(' '), Year4]
        self.assertEqual(3, t([Hour24, Filler(':')], elem_list))

    def testSequenceWithOverlappingStart(self):
        elem_list = [MonthNum(), MonthNum(), Filler('/')]
        sequence = ruleproc.Sequence(MonthNum, Filler('/'))

        self.assertTrue(sequence.is_true(elem_list))
        self.assertEqual(1, ruleproc.Sequence.find(sequence.sequence, elem_list))

    def testSequenceWildcardsAndNoMatch(self):
        elem_list = [MonthNum(), Filler('/'), Year4()]

        self.assertTrue(ruleproc.Sequence('.', '\\D', '\\d').is_true(elem_list))
        self.assertEqual(0, ruleproc.Sequence.find(['.', '\\D', '\\d'], elem_list))
        self.assertFalse(ruleproc.Sequence(DayOfMonth, Year4).is_true(elem_list))
        with self.assertRaises(LookupError):
            ruleproc.Sequence.find([DayOfMonth, Year4], elem_list)

    def testMatch(self):
        t = ruleproc.Sequence.match

        self.assertTrue(t(Hour12, Hour12))
        self.assertTrue(t(Hour12(), Hour12))
        self.assertTrue(t(Hour12, Hour12()))
        self.assertTrue(t(Hour12(), Hour12()))
        self.assertFalse(t(Hour12, Hour24))
        self.assertFalse(t(Hour12(), Hour24))
        self.assertFalse(t(Hour12, Hour24()))
        self.assertFalse(t(Hour12(), Hour24()))

    def testWeekdayWildcards(self):
        t = ruleproc.Sequence.match

        for weekday in (WeekdayLong(), WeekdayShort()):
            self.assertTrue(t(weekday, '\\D'))
            self.assertFalse(t(weekday, '\\d'))

    def testNext(self):
        elem_list = [Filler(' '), DayOfMonth(), Filler('/'), MonthNum(), Hour24(), Year4()]

        next1 = ruleproc.Next(DayOfMonth, MonthNum)
        self.assertTrue(next1.is_true(elem_list))

        next2 = ruleproc.Next(MonthNum, Hour24)
        self.assertTrue(next2.is_true(elem_list))

        next3 = ruleproc.Next(Filler, Year4)
        self.assertFalse(next3.is_true(elem_list))

    def testNextAdjacent(self):
        # Directly adjacent matching elements satisfy Next
        elem_list = [DayOfMonth(), MonthNum()]
        self.assertTrue(ruleproc.Next(DayOfMonth, MonthNum).is_true(elem_list))

    def testNextFillerSeparated(self):
        # Matching elements separated only by Filler instances satisfy Next
        elem_list = [DayOfMonth(), Filler('/'), Filler(' '), MonthNum()]
        self.assertTrue(ruleproc.Next(DayOfMonth, MonthNum).is_true(elem_list))

    def testNextNonFillerBetween(self):
        # A non-filler between the matches makes Next false, including immediately
        # before the right endpoint
        elem_list = [DayOfMonth(), Year4(), MonthNum()]
        self.assertFalse(ruleproc.Next(DayOfMonth, MonthNum).is_true(elem_list))

    def testNextOrderIndependent(self):
        # Endpoints are matched in either direction
        elem_list = [MonthNum(), Filler('/'), DayOfMonth()]
        self.assertTrue(ruleproc.Next(DayOfMonth, MonthNum).is_true(elem_list))
        self.assertTrue(ruleproc.Next(MonthNum, DayOfMonth).is_true(elem_list))

        non_filler = [MonthNum(), Year4(), DayOfMonth()]
        self.assertFalse(ruleproc.Next(DayOfMonth, MonthNum).is_true(non_filler))
        self.assertFalse(ruleproc.Next(MonthNum, DayOfMonth).is_true(non_filler))


class TestTagMostLikely(unittest.TestCase):
    def testTagMostLikely(self):
        examples = ['8/12/2004', '8/14/2004', '8/16/2004', '8/25/2004']
        t = _tag_most_likely

        actual = t(examples)
        expected = [MonthNum(), Filler('/'), DayOfMonth(), Filler('/'), Year4()]

        self.assertListEqual(actual, expected)


class TestTokenizeByCharacterClass(unittest.TestCase):
    def testTokenize(self):
        t = _tokenize_by_character_class

        self.assertListEqual([], t(''))
        self.assertListEqual(['2013', '-', '08', '-', '14'], t('2013-08-14'))
        self.assertListEqual(['Sat', ' ', 'Jan', ' ', '11', ' ', '19', ':', '54', ':', '52', ' ', 'MST', ' ', '2014'],
                             t('Sat Jan 11 19:54:52 MST 2014'))
        self.assertListEqual(['4', '/', '30', '/', '1998', ' ', '4', ':', '52', ' ', 'am'], t('4/30/1998 4:52 am'))
