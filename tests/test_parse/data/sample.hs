module UserManager where

import Data.Maybe (fromMaybe)
import Control.Monad (when)
import qualified Data.Map as Map

-- Type definitions
data User = User
    { userName :: String
    , userAge :: Int
    } deriving (Show, Eq)

data Result a
    = Success a
    | Error String
    deriving (Show)

-- Type class
class Processable a where
    process :: a -> Result a

-- Type class instance
instance Processable User where
    process user@(User _ age)
        | age >= 18 = Success user
        | otherwise = Error "User is underage"

-- Basic function with type signature
createUser :: String -> Int -> User
createUser name age = User name age

-- Pattern matching function
getUserName :: User -> String
getUserName (User name _) = name

-- Guards in function
checkAge :: Int -> String
checkAge age
    | age < 0 = "Invalid age"
    | age < 18 = "Minor"
    | age < 65 = "Adult"
    | otherwise = "Senior"

-- Function with where clause
calculateStats :: User -> (Int, String)
calculateStats user = (ageCategory, status)
    where
        age = userAge user
        ageCategory = age `div` 10 * 10
        status = checkAge age

-- Function using let expression
formatUser :: User -> String
formatUser user =
    let name = userName user
        age = userAge user
    in name ++ " (" ++ show age ++ " years old)"

-- Higher order function
processUsers :: (User -> Result User) -> [User] -> [Result User]
processUsers f = map f

-- Function composition
getProcessedName :: User -> String
getProcessedName = formatName . userName
    where formatName = reverse . map toUpper

-- Curried function
addAge :: Int -> User -> User
addAge years user = user { userAge = userAge user + years }

-- Maybe returning function
findUser :: String -> [User] -> Maybe User
findUser name = foldr check Nothing
    where check user acc
            | userName user == name = Just user
            | otherwise = acc

-- List comprehension
getAdultUsers :: [User] -> [User]
getAdultUsers users = [user | user <- users, userAge user >= 18]

-- Function using case expression
processUserCase :: User -> Result User
processUserCase user = case userAge user of
    age | age < 0 -> Error "Invalid age"
        | age < 18 -> Error "Underage"
        | otherwise -> Success user

-- Partial application example
incrementAge :: User -> User
incrementAge = addAge 1

-- Lambda function example
processWithLog :: User -> IO ()
processWithLog = \user -> do
    putStrLn $ "Processing user: " ++ userName user
    print $ process user

-- Main function to demonstrate usage
main :: IO ()
main = do
    let user1 = createUser "John" 25
        user2 = createUser "Alice" 17
        users = [user1, user2]
    
    putStrLn "Created users:"
    mapM_ (putStrLn . formatUser) users
    
    putStrLn "\nProcessing users:"
    mapM_ (print . process) users
    
    putStrLn "\nAdult users:"
    mapM_ (putStrLn . formatUser) (getAdultUsers users)
    
    putStrLn "\nProcessing with logs:"
    mapM_ processWithLog users
    
    let olderUser1 = incrementAge user1
    putStrLn $ "\nIncremented age for " ++ formatUser olderUser1 