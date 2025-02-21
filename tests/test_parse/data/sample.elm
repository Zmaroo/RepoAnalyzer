module Main exposing (main)

import Browser
import Html exposing (..)
import Html.Attributes exposing (..)
import Html.Events exposing (..)


-- MODEL

type alias User =
    { name : String
    , age : Int
    }

type alias Model =
    { users : List User
    , newUser : User
    }

type Msg
    = AddUser
    | UpdateName String
    | UpdateAge String
    | RemoveUser Int


-- INIT

init : Model
init =
    { users = []
    , newUser = User "" 0
    }


-- UPDATE

update : Msg -> Model -> Model
update msg model =
    case msg of
        AddUser ->
            { model
                | users = model.users ++ [model.newUser]
                , newUser = User "" 0
            }

        UpdateName name ->
            { model
                | newUser = updateName name model.newUser
            }

        UpdateAge ageStr ->
            { model
                | newUser = updateAge ageStr model.newUser
            }

        RemoveUser index ->
            { model
                | users = removeAt index model.users
            }


-- HELPER FUNCTIONS

updateName : String -> User -> User
updateName newName user =
    { user | name = newName }

updateAge : String -> User -> User
updateAge ageStr user =
    { user | age = String.toInt ageStr |> Maybe.withDefault 0 }

removeAt : Int -> List a -> List a
removeAt index list =
    List.take index list ++ List.drop (index + 1) list

isAdult : User -> Bool
isAdult user =
    user.age >= 18

formatUser : User -> String
formatUser user =
    user.name ++ " (" ++ String.fromInt user.age ++ " years old)"

filterAdults : List User -> List User
filterAdults =
    List.filter isAdult

mapToNames : List User -> List String
mapToNames =
    List.map .name


-- VIEW

view : Model -> Html Msg
view model =
    div [ class "container" ]
        [ h1 [] [ text "User Management" ]
        , div [ class "input-group" ]
            [ input
                [ type_ "text"
                , placeholder "Name"
                , value model.newUser.name
                , onInput UpdateName
                ] []
            , input
                [ type_ "number"
                , placeholder "Age"
                , value (String.fromInt model.newUser.age)
                , onInput UpdateAge
                ] []
            , button [ onClick AddUser ] [ text "Add User" ]
            ]
        , div [ class "user-list" ]
            (List.indexedMap viewUser model.users)
        , viewStats model
        ]

viewUser : Int -> User -> Html Msg
viewUser index user =
    div [ class "user-item" ]
        [ text (formatUser user)
        , button
            [ onClick (RemoveUser index)
            , class "remove-button"
            ]
            [ text "Remove" ]
        ]

viewStats : Model -> Html Msg
viewStats model =
    let
        adultCount =
            List.length (filterAdults model.users)

        totalCount =
            List.length model.users
    in
    div [ class "stats" ]
        [ h2 [] [ text "Statistics" ]
        , p [] [ text ("Total users: " ++ String.fromInt totalCount) ]
        , p [] [ text ("Adult users: " ++ String.fromInt adultCount) ]
        ]


-- MAIN

main : Program () Model Msg
main =
    Browser.sandbox
        { init = init
        , update = update
        , view = view
        } 