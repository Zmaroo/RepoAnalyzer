module UserManager where

import Prelude

import Data.Maybe (Maybe(..), fromMaybe)
import Data.Either (Either(..))
import Data.Array (filter)
import Effect (Effect)
import Effect.Console (log)

-- Type aliases
type Name = String
type Age = Int

-- Newtype wrapper
newtype User = User
  { name :: Name
  , age :: Age
  }

-- Type class for processing
class Processable a where
  process :: a -> Either String String

-- Type class instance
instance processableUser :: Processable User where
  process (User { age })
    | age < 0 = Left "Invalid age"
    | age < 18 = Left "Underage"
    | otherwise = Right "Adult user"

-- Record accessor functions
getName :: User -> Name
getName (User { name }) = name

getAge :: User -> Age
getAge (User { age }) = age

-- Smart constructor with validation
createUser :: Name -> Age -> Maybe User
createUser name age
  | age < 0 = Nothing
  | otherwise = Just $ User { name, age }

-- Function with type constraints
formatUser :: forall a. Processable a => a -> String
formatUser user = case process user of
  Left err -> "Error: " <> err
  Right msg -> "Success: " <> msg

-- Higher-order function
processUsers :: forall a. Processable a => Array a -> Array String
processUsers = map formatUser

-- Function composition
getUppercaseName :: User -> String
getUppercaseName = getName >>> toUpper
  where
    toUpper :: String -> String
    toUpper str = str -- Placeholder: PureScript doesn't have a built-in toUpper

-- Monadic function
validateUser :: User -> Effect Unit
validateUser user = do
  log $ "Validating user: " <> getName user
  log $ formatUser user

-- Function with pattern matching
describeAge :: Age -> String
describeAge age
  | age < 0 = "Invalid age"
  | age < 18 = "Minor"
  | age < 65 = "Adult"
  | otherwise = "Senior"

-- Function using Maybe
findUser :: Array User -> Name -> Maybe User
findUser users name = 
  users # filter (\user -> getName user == name) # head
  where
    head [] = Nothing
    head (x:_) = Just x

-- Function with type class constraints
countAdults :: forall a. Processable a => Array a -> Int
countAdults users = 
  users 
    # filter isAdult
    # length
  where
    isAdult user = case process user of
      Right "Adult user" -> true
      _ -> false

-- Main program
main :: Effect Unit
main = do
  -- Create users
  let user1 = createUser "John" 25
      user2 = createUser "Alice" 17
      users = [user1, user2] # catMaybes
  
  -- Test basic functions
  log "Users:"
  for_ users \user -> do
    log $ getName user <> " (" <> show (getAge user) <> ")"
  
  -- Test processing
  log "\nProcessing results:"
  for_ (processUsers users) \result -> do
    log result
  
  -- Test validation
  log "\nValidation:"
  for_ users validateUser
  
  -- Test age description
  log "\nAge descriptions:"
  for_ users \user -> do
    log $ getName user <> ": " <> describeAge (getAge user)
  
  -- Test user finding
  log "\nFinding user:"
  case findUser users "John" of
    Just user -> log $ "Found: " <> getName user
    Nothing -> log "User not found"
  
  -- Test adult counting
  log "\nStatistics:"
  log $ "Adult count: " <> show (countAdults users)

-- Helper functions
catMaybes :: forall a. Array (Maybe a) -> Array a
catMaybes arr = arr # filter isJust # map fromJust
  where
    isJust (Just _) = true
    isJust Nothing = false
    fromJust (Just x) = x
    fromJust Nothing = unsafeCrashWith "Impossible: fromJust Nothing"

for_ :: forall a m. Applicative m => Array a -> (a -> m Unit) -> m Unit
for_ = flip traverse_ 