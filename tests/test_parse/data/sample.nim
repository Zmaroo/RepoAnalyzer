type
  User = object
    name: string
    age: int

proc createUser(name: string, age: int): User =
  result = User(name: name, age: age)

proc isAdult(user: User): bool =
  result = user.age >= 18

proc formatUser(user: User): string =
  result = user.name & " (" & $user.age & " years old)" 