(ns user-manager.core
  (:require [clojure.string :as str]))

;; Record definition
(defrecord User [name age])

;; Protocol definition
(defprotocol UserProcessor
  (process-user [this])
  (format-user [this]))

;; Extend protocol to User record
(extend-protocol UserProcessor
  User
  (process-user [{:keys [age] :as user}]
    (cond
      (neg? age) {:error "Invalid age"}
      (< age 18) {:error "Underage"}
      :else {:ok user}))
  
  (format-user [{:keys [name age]}]
    (format "%s (%d years old)" name age)))

;; Basic function with type hints
(defn create-user
  "Create a new user with the given name and age"
  [^String name ^Long age]
  (->User name age))

;; Function with pre/post conditions
(defn update-age
  "Update user's age with validation"
  [user new-age]
  {:pre [(>= new-age 0)]
   :post [(>= (:age %) 0)]}
  (assoc user :age new-age))

;; Multi-arity function
(defn create-greeting
  "Create a greeting message"
  ([name] (create-greeting "Hello" name))
  ([prefix name]
   (format "%s, %s!" prefix name)))

;; Higher-order function
(defn process-users
  "Process a collection of users with the given function"
  [f users]
  (map f users))

;; Function returning function (closure)
(defn age-checker
  "Create a function that checks if a user meets the minimum age"
  [min-age]
  (fn [user]
    (>= (:age user) min-age)))

;; Function using threading macro
(defn process-name
  "Process a name using threading macro"
  [name]
  (-> name
      str/trim
      str/lower-case
      str/capitalize))

;; Function with destructuring
(defn analyze-user
  "Analyze user data using destructuring"
  [{:keys [name age] :as user}]
  (let [result (process-user user)]
    (if (:ok result)
      (format "Valid user: %s, age %d" name age)
      (format "Invalid user: %s" (:error result)))))

;; Function using loop/recur
(defn find-user
  "Find a user by name using recursion"
  [name users]
  (loop [remaining users]
    (when (seq remaining)
      (let [user (first remaining)]
        (if (= (:name user) name)
          user
          (recur (rest remaining)))))))

;; Function using reduce
(defn average-age
  "Calculate average age of users"
  [users]
  (let [total (count users)]
    (if (pos? total)
      (/ (reduce + (map :age users)) total)
      0)))

;; Function using comp
(def get-uppercase-name
  "Get user's name in uppercase using function composition"
  (comp str/upper-case :name))

;; Function using partial
(def adult-checker
  "Check if user is adult (partial application)"
  (partial (age-checker 18)))

;; Main execution function
(defn run-examples
  "Run example usage of all functions"
  []
  (let [user1 (create-user "John" 25)
        user2 (create-user "Alice" 17)
        users [user1 user2]]
    
    ;; Test basic functions
    (println "Users:")
    (doseq [user users]
      (println (format-user user)))
    
    ;; Test processing
    (println "\nProcessing results:")
    (doseq [result (process-users process-user users)]
      (println result))
    
    ;; Test higher-order functions
    (println "\nAdult users:")
    (doseq [user (filter adult-checker users)]
      (println (format-user user)))
    
    ;; Test name processing
    (println "\nProcessed names:")
    (doseq [user users]
      (println (process-name (:name user))))
    
    ;; Test analysis
    (println "\nUser analysis:")
    (doseq [user users]
      (println (analyze-user user)))
    
    ;; Test average age
    (println "\nAverage age:" (average-age users))
    
    ;; Test uppercase names
    (println "\nUppercase names:")
    (doseq [user users]
      (println (get-uppercase-name user)))))

;; Run examples
(run-examples) 