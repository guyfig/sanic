from collections import defaultdict, namedtuple

from sanic.constants import HTTP_METHODS
from sanic.views import CompositionView

FutureRoute = namedtuple('Route', ['handler', 'uri', 'methods', 'host'])
FutureListener = namedtuple('Listener', ['handler', 'uri', 'methods', 'host'])
FutureMiddleware = namedtuple('Route', ['middleware', 'args', 'kwargs'])
FutureException = namedtuple('Route', ['handler', 'args', 'kwargs'])
FutureStatic = namedtuple('Route',
                          ['uri', 'file_or_directory', 'args', 'kwargs'])


class Blueprint:
    def __init__(self, name, url_prefix=None, host=None):
        """Create a new blueprint

        :param name: unique name of the blueprint
        :param url_prefix: URL to be prefixed before all route URLs
        """
        self.name = name
        self.url_prefix = url_prefix
        self.host = host

        self.routes = []
        self.exceptions = []
        self.listeners = defaultdict(list)
        self.middlewares = []
        self.statics = []

    def register(self, app, options):
        """Register the blueprint to the sanic app."""

        url_prefix = options.get('url_prefix', self.url_prefix)

        # Routes
        for future in self.routes:
            # attach the blueprint name to the handler so that it can be
            # prefixed properly in the router
            future.handler.__blueprintname__ = self.name
            # Prepend the blueprint URI prefix if available
            uri = url_prefix + future.uri if url_prefix else future.uri
            app.route(
                uri=uri,
                methods=future.methods,
                host=future.host or self.host
                )(future.handler)

        # Middleware
        for future in self.middlewares:
            if future.args or future.kwargs:
                app.middleware(*future.args,
                               **future.kwargs)(future.middleware)
            else:
                app.middleware(future.middleware)

        # Exceptions
        for future in self.exceptions:
            app.exception(*future.args, **future.kwargs)(future.handler)

        # Static Files
        for future in self.statics:
            # Prepend the blueprint URI prefix if available
            uri = url_prefix + future.uri if url_prefix else future.uri
            app.static(uri, future.file_or_directory,
                       *future.args, **future.kwargs)

        # Event listeners
        for event, listeners in self.listeners.items():
            for listener in listeners:
                app.listener(event)(listener)

    def route(self, uri, methods=frozenset({'GET'}), host=None):
        """Create a blueprint route from a decorated function.

        :param uri: endpoint at which the route will be accessible.
        :param methods: list of acceptable HTTP methods.
        """
        def decorator(handler):
            route = FutureRoute(handler, uri, methods, host)
            self.routes.append(route)
            return handler
        return decorator

    def add_route(self, handler, uri, methods=frozenset({'GET'}), host=None):
        """Create a blueprint route from a function.

        :param handler: function for handling uri requests. Accepts function,
                        or class instance with a view_class method.
        :param uri: endpoint at which the route will be accessible.
        :param methods: list of acceptable HTTP methods.
        :return: function or class instance
        """
        # Handle HTTPMethodView differently
        if hasattr(handler, 'view_class'):
            methods = set()

            for method in HTTP_METHODS:
                if getattr(handler.view_class, method.lower(), None):
                    methods.add(method)

        # handle composition view differently
        if isinstance(handler, CompositionView):
            methods = handler.handlers.keys()

        self.route(uri=uri, methods=methods, host=host)(handler)
        return handler

    def listener(self, event):
        """Create a listener from a decorated function.

        :param event: Event to listen to.
        """
        def decorator(listener):
            self.listeners[event].append(listener)
            return listener
        return decorator

    def middleware(self, *args, **kwargs):
        """Create a blueprint middleware from a decorated function."""
        def register_middleware(_middleware):
            future_middleware = FutureMiddleware(_middleware, args, kwargs)
            self.middlewares.append(future_middleware)
            return _middleware

        # Detect which way this was called, @middleware or @middleware('AT')
        if len(args) == 1 and len(kwargs) == 0 and callable(args[0]):
            middleware = args[0]
            args = []
            return register_middleware(middleware)
        else:
            return register_middleware

    def exception(self, *args, **kwargs):
        """Create a blueprint exception from a decorated function."""
        def decorator(handler):
            exception = FutureException(handler, args, kwargs)
            self.exceptions.append(exception)
            return handler
        return decorator

    def static(self, uri, file_or_directory, *args, **kwargs):
        """Create a blueprint static route from a decorated function.

        :param uri: endpoint at which the route will be accessible.
        :param file_or_directory: Static asset.
        """
        static = FutureStatic(uri, file_or_directory, args, kwargs)
        self.statics.append(static)

    # Shorthand method decorators
    def get(self, uri, host=None):
        return self.route(uri, methods=["GET"], host=host)

    def post(self, uri, host=None):
        return self.route(uri, methods=["POST"], host=host)

    def put(self, uri, host=None):
        return self.route(uri, methods=["PUT"], host=host)

    def head(self, uri, host=None):
        return self.route(uri, methods=["HEAD"], host=host)

    def options(self, uri, host=None):
        return self.route(uri, methods=["OPTIONS"], host=host)

    def patch(self, uri, host=None):
        return self.route(uri, methods=["PATCH"], host=host)

    def delete(self, uri, host=None):
        return self.route(uri, methods=["DELETE"], host=host)
