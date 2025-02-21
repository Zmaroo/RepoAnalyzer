module user_manager
  implicit none
  
  type :: user
    character(len=20) :: name
    integer :: age
  end type user
  
contains
  logical function is_adult(u)
    type(user), intent(in) :: u
    is_adult = u%age >= 18
  end function is_adult
end module user_manager 