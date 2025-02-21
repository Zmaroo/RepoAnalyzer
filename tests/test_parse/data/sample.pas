program UserManager;

type
  TUser = record
    Name: string;
    Age: Integer;
  end;

function IsAdult(User: TUser): Boolean;
begin
  Result := User.Age >= 18;
end;

procedure ProcessUser(User: TUser);
begin
  if IsAdult(User) then
    WriteLn('Processing adult user: ', User.Name)
  else
    WriteLn('Processing minor user: ', User.Name);
end;

begin
  // Main program
end. 