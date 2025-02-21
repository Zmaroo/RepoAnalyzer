with Ada.Text_IO; use Ada.Text_IO;
with Ada.Integer_Text_IO; use Ada.Integer_Text_IO;
with Ada.Strings.Unbounded; use Ada.Strings.Unbounded;

procedure User_Manager is
   -- Type definitions
   type Age_Type is range 0 .. 150;
   
   type User is record
      Name : Unbounded_String;
      Age  : Age_Type;
   end record;
   
   type User_Array is array (Positive range <>) of User;
   
   -- Exception declaration
   Invalid_Age : exception;
   
   -- Function to create a user
   function Create_User (Name : String; Age : Integer) return User is
   begin
      if Age < 0 then
         raise Invalid_Age with "Age cannot be negative";
      end if;
      
      return (Name => To_Unbounded_String(Name),
              Age  => Age_Type(Age));
   end Create_User;
   
   -- Procedure to print user info
   procedure Print_User (U : User) is
   begin
      Put(To_String(U.Name));
      Put(" (");
      Put(Integer(U.Age), 0);
      Put_Line(" years old)");
   end Print_User;
   
   -- Function with out parameter
   procedure Get_User_Info (U : User; Name : out String; Age : out Integer) is
   begin
      Name := To_String(U.Name);
      Age := Integer(U.Age);
   end Get_User_Info;
   
   -- Generic function
   generic
      Min_Age : Age_Type;
   function Check_Age (U : User) return Boolean;
   
   function Check_Age (U : User) return Boolean is
   begin
      return U.Age >= Min_Age;
   end Check_Age;
   
   -- Instantiate generic function
   function Is_Adult is new Check_Age(Min_Age => 18);
   
   -- Function that returns an access type
   type User_Access is access User;
   
   function Create_User_Access (Name : String; Age : Integer) return User_Access is
   begin
      return new User'(Create_User(Name, Age));
   end Create_User_Access;
   
   -- Procedure with array parameter
   procedure Process_Users (Users : User_Array) is
   begin
      for I in Users'Range loop
         Put("Processing user: ");
         Print_User(Users(I));
      end loop;
   end Process_Users;
   
   -- Function returning multiple values using out parameters
   procedure Analyze_Age (U : User; 
                         Is_Adult : out Boolean; 
                         Message : out String) is
   begin
      Is_Adult := U.Age >= 18;
      if Is_Adult then
         Message := "Adult user     ";
      else
         Message := "Underage user  ";
      end if;
   end Analyze_Age;
   
   -- Protected type for thread-safe user processing
   protected User_Processor is
      procedure Process_User (U : in User);
      function Get_Processed_Count return Natural;
   private
      Processed_Count : Natural := 0;
   end User_Processor;
   
   protected body User_Processor is
      procedure Process_User (U : in User) is
      begin
         Put_Line("Processing in protected object: ");
         Print_User(U);
         Processed_Count := Processed_Count + 1;
      end Process_User;
      
      function Get_Processed_Count return Natural is
      begin
         return Processed_Count;
      end Get_Processed_Count;
   end User_Processor;
   
   -- Main program variables
   User1, User2 : User;
   Users : User_Array(1..2);
   User_Ptr : User_Access;
   Is_User_Adult : Boolean;
   Status_Message : String(1..13);
   
begin
   -- Create users
   User1 := Create_User("John", 25);
   User2 := Create_User("Alice", 17);
   Users := (User1, User2);
   
   -- Test basic functions
   Put_Line("Created users:");
   Print_User(User1);
   Print_User(User2);
   
   -- Test array processing
   New_Line;
   Put_Line("Processing users:");
   Process_Users(Users);
   
   -- Test age checking
   New_Line;
   Put_Line("Age check results:");
   for U of Users loop
      if Is_Adult(U) then
         Put_Line(To_String(U.Name) & " is an adult");
      else
         Put_Line(To_String(U.Name) & " is not an adult");
      end if;
   end loop;
   
   -- Test access type
   New_Line;
   Put_Line("Testing access type:");
   User_Ptr := Create_User_Access("Bob", 30);
   Print_User(User_Ptr.all);
   
   -- Test protected object
   New_Line;
   Put_Line("Testing protected object:");
   User_Processor.Process_User(User1);
   Put_Line("Processed count: " & 
            Integer'Image(User_Processor.Get_Processed_Count));
   
   -- Test multiple out parameters
   New_Line;
   Put_Line("Testing age analysis:");
   for U of Users loop
      Analyze_Age(U, Is_User_Adult, Status_Message);
      Put_Line(To_String(U.Name) & ": " & Status_Message);
   end loop;
   
exception
   when Invalid_Age =>
      Put_Line("Error: Invalid age provided");
   when others =>
      Put_Line("Unexpected error occurred");
end User_Manager; 