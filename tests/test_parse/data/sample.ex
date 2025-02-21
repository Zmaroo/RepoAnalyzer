defmodule UserManager do
  # Module attribute
  @default_age 18

  # Public function with pattern matching
  def process_user(%{name: name, age: age} = user) when age >= @default_age do
    IO.puts("Processing adult user: #{name}")
    {:ok, user}
  end

  def process_user(%{name: name}) do
    IO.puts("Processing minor user: #{name}")
    {:error, :underage}
  end

  # Private function
  defp validate_age(age) when is_integer(age) and age > 0 do
    {:ok, age}
  end

  defp validate_age(_), do: {:error, :invalid_age}

  # Function with default arguments
  def create_user(name, age \\ @default_age) do
    case validate_age(age) do
      {:ok, valid_age} -> %{name: name, age: valid_age}
      error -> error
    end
  end

  # Anonymous function usage
  def process_list(list) do
    Enum.map(list, fn item ->
      String.upcase(item)
    end)
  end

  # Function returning anonymous function
  def create_greeter(greeting) do
    fn name -> "#{greeting}, #{name}!" end
  end

  # Function with guard clauses
  def check_age(age) when is_integer(age) and age >= @default_age do
    :adult
  end

  def check_age(age) when is_integer(age) do
    :minor
  end

  def check_age(_) do
    :invalid
  end

  # Pipe operator example function
  def process_name(name) do
    name
    |> String.trim()
    |> String.capitalize()
    |> String.replace(" ", "_")
  end

  # Function with multiple clauses and pattern matching
  def handle_result({:ok, value}), do: "Success: #{value}"
  def handle_result({:error, reason}), do: "Error: #{reason}"
  def handle_result(_), do: "Unknown result"

  # Function using comprehension
  def process_users(users) do
    for user <- users,
        Map.has_key?(user, :name),
        do: process_user(user)
  end
end

# Protocol implementation example
defprotocol Formatter do
  def format(value)
end

defimpl Formatter, for: Map do
  def format(map) do
    map
    |> Map.to_list()
    |> Enum.map(fn {k, v} -> "#{k}: #{v}" end)
    |> Enum.join(", ")
  end
end

# Example usage
defmodule Example do
  def run do
    user = UserManager.create_user("John", 25)
    UserManager.process_user(user)

    greeter = UserManager.create_greeter("Hello")
    IO.puts(greeter.("Alice"))

    users = [
      %{name: "Bob", age: 30},
      %{name: "Alice", age: 25},
      %{name: "Charlie", age: 15}
    ]
    UserManager.process_users(users)
  end
end 