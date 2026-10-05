"""Observable contracts for the ordinary-programming language foundation."""
import shutil
import unittest

from myrk.lexer import MyrkError, lex
from myrk.parser import parse
from myrk.semantics import check
from test_buffers import native, program


class LanguageSyntaxTests(unittest.TestCase):
    def test_nested_block_comment_locations(self):
        tokens = lex('/* outer\n /* inner */ done */\nprint(42);')
        self.assertEqual((tokens[0].text, tokens[0].pos.line, tokens[0].pos.column),
                         ('print', 3, 1))

    def test_unterminated_block_comment(self):
        with self.assertRaisesRegex(MyrkError, 'unterminated block comment') as raised:
            lex('\n  /* still open')
        self.assertEqual((raised.exception.pos.line, raised.exception.pos.column), (2, 3))

    def test_scientific_and_integer_float_suffixes(self):
        tokens = lex('1e3 2.5E-2f32 3f64 4f32 0..10')
        self.assertEqual([t.kind for t in tokens[:-1]],
                         ['float', 'float', 'float', 'float', 'int', '..', 'int'])

    def test_malformed_exponents(self):
        for literal in ('1e', '1e+', '1.0e-'):
            with self.subTest(literal=literal), self.assertRaisesRegex(MyrkError, 'exponent'):
                lex(literal)

    def test_exact_initializer_type_inference(self):
        module = check(parse(program('let a = 1; let b = 2f32; let c = 3e-2; var d = true;')))
        self.assertEqual([s.data[1] for s in module.procedures[0].body[:4]],
                         ['i32', 'f32', 'f64', 'bool'])

    def test_inference_keeps_type_and_immutability_errors(self):
        for body, error in [('var x = 1; x = 2.0;', 'expected i32'),
                            ('let x = 1; x = 2;', 'immutable'),
                            ('let x = x;', 'unknown variable')]:
            with self.subTest(body=body), self.assertRaisesRegex(MyrkError, error):
                check(parse(program(body)))


@unittest.skipUnless(shutil.which('cc') or shutil.which('clang'), 'C compiler required')
class LanguageNativeTests(unittest.TestCase):
    def test_shorter_declarations_and_scientific_literals(self):
        result = native(program('/* note */ let a = 2f32; var b = 1e2; b = b + 0.5; print(a); print(b);'))
        self.assertEqual((result.returncode, result.stdout), (0, '2\n100.5\n'))


if __name__ == '__main__':
    unittest.main()
