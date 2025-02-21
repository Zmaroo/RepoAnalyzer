-module(user_manager).
-export([create_user/2, process_user/1, handle_users/1, start/0]).

% Record definition
-record(user, {name, age}).

% Type specifications
-type user() :: #user{}.
-type result() :: {ok, user()} | {error, term()}.

% Function with pattern matching and guards
-spec create_user(string(), integer()) -> user().
create_user(Name, Age) when is_list(Name), is_integer(Age), Age >= 0 ->
    #user{name = Name, age = Age}.

% Function with multiple clauses
-spec process_user(user()) -> result().
process_user(#user{name = Name, age = Age}) when Age >= 18 ->
    io:format("Processing adult user: ~s~n", [Name]),
    {ok, #user{name = Name, age = Age}};
process_user(#user{name = Name}) ->
    io:format("Processing minor user: ~s~n", [Name]),
    {error, underage}.

% Function using list comprehension
-spec handle_users([user()]) -> [result()].
handle_users(Users) ->
    [process_user(User) || User <- Users].

% Function using case expression
validate_age(Age) ->
    case Age of
        A when is_integer(A), A >= 0 -> {ok, A};
        _ -> {error, invalid_age}
    end.

% Private helper function (not exported)
format_user(#user{name = Name, age = Age}) ->
    lists:flatten(io_lib:format("~s (~p years old)", [Name, Age])).

% Function with try-catch
safe_process_user(User) ->
    try process_user(User) of
        Result -> Result
    catch
        error:Error -> {error, Error};
        _:_ -> {error, unknown_error}
    end.

% Function using higher-order functions
process_names(Names) ->
    lists:map(fun(Name) -> string:uppercase(Name) end, Names).

% Function returning fun
create_greeter(Greeting) ->
    fun(Name) -> Greeting ++ ", " ++ Name ++ "!" end.

% Function with message passing
start_user_processor() ->
    spawn(fun() -> user_processor_loop() end).

user_processor_loop() ->
    receive
        {process, User} ->
            process_user(User),
            user_processor_loop();
        stop ->
            ok
    end.

% Main function to demonstrate usage
start() ->
    % Create some users
    User1 = create_user("John", 25),
    User2 = create_user("Alice", 17),
    
    % Process individual users
    process_user(User1),
    process_user(User2),
    
    % Process list of users
    Users = [User1, User2],
    Results = handle_users(Users),
    io:format("Processing results: ~p~n", [Results]),
    
    % Try higher-order functions
    Names = ["bob", "alice", "charlie"],
    UpperNames = process_names(Names),
    io:format("Uppercase names: ~p~n", [UpperNames]),
    
    % Try function generator
    Greeter = create_greeter("Hello"),
    Greeting = Greeter("Dave"),
    io:format("~s~n", [Greeting]),
    
    % Try message passing
    Pid = start_user_processor(),
    Pid ! {process, User1},
    Pid ! stop,
    
    ok. 