from django.test import TransactionTestCase, TestCase, RequestFactory
from django.shortcuts import render
from django.db import IntegrityError
import django_ecommerce.settings as settings
from payments.views import sign_in, sign_out
from payments.views import soon, register, Customer
from payments.models import User, UnpaidUsers
from payments.forms import SigninForm, UserForm
import unittest
import mock
from django.core.urlresolvers import resolve
import socket
import copy


def get_mock_cust():
    class mock_cust():
        @property
        def id(self):
            return 1234
    return mock_cust()


class ViewTesterMixin(object):

    @classmethod
    def setupViewTester(cls, url, view_func, expected_html_path,
                        expected_html_context,
                        status_code=200,
                        session={}):
        request_factory = RequestFactory()
        cls.request = request_factory.get(url)
        cls.request.session = session
        cls.status_code = status_code
        cls.url = url
        cls.view_func = staticmethod(view_func)

        expected_html = b""
        if expected_html_path and expected_html_context:
            response = render(
                cls.request,
                expected_html_path,
                expected_html_context,
            )
            expected_html = response.content
        cls.expected_html = expected_html


    def test_resolves_to_correct_view(self):
        test_view = resolve(self.url)
        self.assertEqual(test_view.func, self.view_func)

    def test_returns_appropriate_respose_code(self):
        resp = self.view_func(self.request)
        self.assertEqual(resp.status_code, self.status_code)

    def test_returns_correct_html(self):
        resp = self.view_func(self.request)
        self.assertEqual(resp.content, self.expected_html)


class SignInPageTests(TestCase, ViewTesterMixin):

    @classmethod
    def setUpClass(cls):
        super(SignInPageTests, cls).setUpClass()
        page = 'payments/sign_in.html'
        context = {
                            'form': SigninForm(),
                            'user': None
                        }

        ViewTesterMixin.setupViewTester(
            '/sign_in',
            sign_in,
            page,
            context,
        )


class SignOutPageTests(TestCase, ViewTesterMixin):

    @classmethod
    def setUpClass(cls):
        super(SignOutPageTests, cls).setUpClass()
        ViewTesterMixin.setupViewTester(
            '/sign_out',
            sign_out,
            None, None,  # a redirect will return no html
            status_code=302,
            session={"user": "dummy"},
        )

    def setUp(self):
        #sign_out clears the session, so let's reset it everytime
        self.request.session = {"user": "dummy"}


class RegisterPageTests(TestCase, ViewTesterMixin):

    @classmethod
    def setUpClass(cls):
        super(RegisterPageTests, cls).setUpClass()
        page = 'payments/register.html'
        the_form = UserForm()
        context =    {
                'form':the_form,
                'months': list(range(1, 12)),
                'publishable': settings.STRIPE_PUBLISHABLE,
                'soon': soon(),
                'user': None,
                'years': list(range(2011, 2036)),
            }
        ViewTesterMixin.setupViewTester(
            '/register',
            register,
            page,
            context,
            session={"user": "dummy"},
        )

    def setUp(self):
        self.req = copy.copy(self.request)

    def test_returns_correct_html(self):
        # overwrite the one in ViewTesterMixin
        resp = self.view_func(self.req)
        self.assertTrue(b"<h1>Register Today!</h1>" in resp.content)

    def test_registering_user_when_stripe_is_down(self):
        # copy the class level request so we don't effect other tests  
        req = copy.copy(self.request)
        req.session = {}
        req.method = 'POST'
        req.POST = {
            'email': 'python@rocks.com',
            'name': 'pyRock',
            'stripe_token': '...',
            'last_4_digits': '4242',
            'password': 'bad_password',
            'ver_password': 'bad_password',
        }

        # mock out Stripe and ask it to throw a connection error
        with mock.patch(
            'stripe.Customer.create',
            side_effect=socket.error("Can't connect to Stripe")
        ) as stripe_mock:

            # run the test
            register(req)

            # assert there is a record in the database without Stripe id.
            users = User.objects.filter(email="python@rocks.com")
            self.assertEquals(len(users), 1)
            self.assertEquals(users[0].stripe_id, '')

            # check the associated table got updated.
            unpaid = UnpaidUsers.objects.filter(email="python@rocks.com")
            self.assertEquals(len(unpaid),1)
            self.assertIsNotNone(unpaid[0].last_notification)

    def test_invalid_form_returns_registration_page(self):
        with mock.patch('payments.forms.UserForm.is_valid') as user_mock:

            user_mock.return_value = False

            self.req.method = 'POST'
            self.req.POST = None
            resp = register(self.req)
            self.assertEqual(resp.content, self.expected_html)

            # make sure that we did indeed call our is_valid function
            self.assertEqual(user_mock.call_count, 1)



    @mock.patch('payments.views.Customer.create', return_value=get_mock_cust())
    def test_registering_new_user_returns_succesfully(self, stripe_mock):

        self.req.session = {}
        self.req.method = 'POST'
        self.req.POST = {
            'email': 'python@rocks.com',
            'name': 'pyRock',
            'stripe_token': '...',
            'last_4_digits': '4242',
            'password': 'bad_password',
            'ver_password': 'bad_password',
        }

        resp = register(self.req)

        self.assertEqual(resp.content, b"")
        self.assertEqual(resp.status_code, 302)

        users = User.objects.filter(email="python@rocks.com")
        self.assertEqual(len(users), 1)
        self.assertEqual(users[0].stripe_id, '1234')


    def get_MockUserForm(self):
        from django import forms

        class MockUserForm(forms.Form):

            def is_valid(self):
                return True

            @property
            def cleaned_data(self):
                return {
                    'email': 'python@rocks.com',
                    'name': 'pyRock',
                    'stripe_token': '...',
                    'last_4_digits': '4242',
                    'password': 'bad_password',
                    'ver_password': 'bad_password',
                }

            def addError(self, error):
                pass

        return MockUserForm()

    @mock.patch('payments.views.UserForm', get_MockUserForm)
    @mock.patch('payments.models.User.save', side_effect=IntegrityError)
    def test_registering_user_twice_cause_error_msg(self, save_mock):

        #create the request used to test the view
        self.req.session = {}
        self.req.method = 'POST'
        self.req.POST = {}

        #create the expected html
        html = render(
            self.req,
            'payments/register.html',
            {
                'form': self.get_MockUserForm(),
                'months': list(range(1, 12)),
                'publishable': settings.STRIPE_PUBLISHABLE,
                'soon': soon(),
                'user': None,
                'years': list(range(2011, 2036)),
            },
        )

        #mock out stripe so we don't hit their server
        with mock.patch('payments.views.Customer') as stripe_mock:

            config = {'create.return_value': mock.Mock()}
            stripe_mock.configure_mock(**config)

            #run the test
            resp = register(self.req)

            #verify that we did things correctly
            self.assertEqual(resp.content, html.content)
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(self.req.session, {})

            #assert there is no records in the database.
            users = User.objects.filter(email="python@rocks.com")
            self.assertEqual(len(users), 0)


    @mock.patch('payments.models.UnpaidUsers.save', side_effect=IntegrityError)
    def test_registering_user_when_strip_is_down_all_or_nothing(self, save_mock):

        #create the request used to test the view
        self.req.session = {}
        self.req.method = 'POST'
        self.req.POST = {
            'email': 'python@rocks.com',
            'name': 'pyRock',
            'stripe_token': '...',
            'last_4_digits': '4242',
            'password': 'bad_password',
            'ver_password': 'bad_password',
        }

        #mock out stripe and ask it to throw a connection error
        with mock.patch(
            'stripe.Customer.create',
            side_effect=socket.error("can't connect to stripe")
        ) as stripe_mock:

            #run the test
            resp = register(self.req)

            #assert there is no new record in the database
            users = User.objects.filter(email="python@rocks.com")
            self.assertEquals(len(users), 0)

            #check the associated table has no updated data
            unpaid = UnpaidUsers.objects.filter(email="python@rocks.com")
            self.assertEquals(len(unpaid), 0)

class RegisterPageOnTransactionCommitTests(TransactionTestCase):

    def setUp(self):
        request_factory = RequestFactory()
        self.req = request_factory.get('/register')


    @mock.patch('payments.views.Customer.create', return_value=get_mock_cust())
    def test_registering_user_triggers_thankyou(self, stripe_mock):

        #create the request used to test the view
        self.req.session = {}
        self.req.method = 'POST'
        self.req.POST = {
            'email': 'python@rocks.com',
            'name': 'pyRock',
            'stripe_token': '...',
            'last_4_digits': '4242',
            'password': 'bad_password',
            'ver_password': 'bad_password',
        }

        with mock.patch('payments.views.send_thankyou') as thankyou_mock:
            #run the test
            resp = register(self.req)
            thankyou_mock.assert_called_once_with('python@rocks.com')