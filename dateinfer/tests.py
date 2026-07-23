import unittest
from datetime import datetime
import dateinfer
from dateinfer.date_elements import *
from dateinfer.infer import infer, _mode, _most_restrictive, _tag_most_likely, _percent_match, _tokenize_by_character_class
import dateinfer.ruleproc as ruleproc
import yaml


def load_tests(loader, standard_tests, ignored):
    """
    Return a TestSuite containing standard_tests plus generated test cases
    """
    suite = unittest.TestSuite()
    suite.addTests(standard_tests)

    with open('examples.yaml', 'r') as f:
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


class TestUTCOffsets(unittest.TestCase):
    def testColonDelimitedOffsetsParseWithInferredFormat(self):
        examples = ['2024-01-13T23:10:55+04:00', '2025-11-27T16:45:30-05:30']

        for example in examples:
            inferred = infer([example])
            self.assertEqual('%Y-%m-%dT%H:%M:%S%z', inferred)
            datetime.strptime(example, inferred)

    def testCompactOffsetsRemainSupported(self):
        examples = ['2014-01-11T12:21:05+0400', '2015-02-16T16:05:31-0400']

        self.assertEqual('%Y-%m-%dT%H:%M:%S%z', infer(examples))


class TestYearFirstDates(unittest.TestCase):
    def testIsoDatetimeHourIsNotRewrittenAsDay(self):
        self.assertEqual('%Y-%m-%dT%I:%M:%S', infer(['2014-01-11T12:21:05']))


class TestMode(unittest.TestCase):
    def testMode(self):
        self.assertEqual(5, _mode([1, 3, 4, 5, 6, 5, 2, 5, 3]))
        self.assertEqual(2, _mode([1, 2, 2, 3, 3]))  # with ties, pick least value


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
