       IDENTIFICATION DIVISION.
       PROGRAM-ID. USER-MANAGER.
       
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 USER-RECORD.
          05 USER-NAME    PIC X(20).
          05 USER-AGE     PIC 9(3).
       
       PROCEDURE DIVISION.
           DISPLAY "Enter user name: "
           ACCEPT USER-NAME
           DISPLAY "Enter user age: "
           ACCEPT USER-AGE. 