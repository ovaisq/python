library(RPostgres)
library(DBI)
library(dplyr)
library(ggplot2)

#TODO: read this from config file
db_name = '<db name>'
db_host = '<db host>'  
db_port = 5432
db_user = '<db user>'
db_pass = '<db user password>'

# connect to database
tryCatch({
  con <- dbConnect(RPostgres::Postgres(), 
                      dbname = db_name,
                      host = db_host, 
                      port = db_port,
                      user = db_user, 
                      password = db_pass)
},
error=function(cond) {
  print("Unable to connect to Database.")
})

#read postgresql table
awscosts <- dbReadTable(con,'costs')

# dataframe
result <- awscosts %>%
  filter(timestamp == max(timestamp) & # latest timestamp for a given day
           time_period >= '2023-09-01' & # TODO: parameterize this 
           time_period < '2023-10-01' & # exclusive value. TODO: parameterize this
           cost_type == 'AmortizedCost') %>% # TODO: do this for various cost types
  group_by(time_period, aws_service) %>%
  summarize(total_amount = sum(amount)) %>%
  arrange(time_period)

# bar graph
ggplot(result, aes(x = time_period, y = total_amount, fill = aws_service)) +
  geom_bar(stat = "identity", position = "stack") +
  geom_text(aes(label = round(total_amount, digits=3)), check_overlap = TRUE, angle = 90)
  labs(title = "Daily AWS Service Amortized Costs",
       x = "Time Period",
       y = "Total Amount") +
  theme_minimal()
