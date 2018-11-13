import math
from collections import namedtuple

Date = namedtuple('Date', 'day month year')
Time = namedtuple('Time', 'hour minute')


class Clock:
    
    def __init__(self, hours_in_day=24, minutes_in_hour=60, hour=0, minute=0):
        self.hours_in_day = hours_in_day
        self.minutes_in_hour = minutes_in_hour

        self.hour = hour
        self.minute = minute

    def __str__(self):
        return f"{self.hour:02}:{self.minute:02}"

    def adjust_time(self, hours=0, minutes=0):
        new_minute = (self.minute + minutes) % self.minutes_in_hour
        new_hour = (((self.hour + hours) + 
                     ((self.minute + minutes) // self.minutes_in_hour)) % 
                     self.hours_in_day)

        self.hour = new_hour
        self.minute = new_minute


class Calendar:

    def __init__(self, cal_data):
        self.cal_data = cal_data
        self.year = cal_data['default_year']
        self.month = cal_data['default_month']
        self.day = cal_data['default_day']

    def __str__(self):
        if self.days_in_month(self.month, self.year) > 1:
            return f"{self.day} {self.month} {self.year}"
        return f"{self.month} {self.year}"

    def days_in_year(self, year):
        days = 0
        for month in self.cal_data['months'].values():
            days += month.get('leap_year_days', month['days']) \
                    if self.is_leap_year(year) \
                    else month['days']
        return days

    def days_in_month(self, month, year):
        month = month.lower()
        days = self.cal_data['months'][month]['days']
        if self.is_leap_year(year):
            return self.cal_data['months'][month].get('leap_year_days', days)
        return days
    
    def is_leap_year(self, year):
        leap_year_rule = self.cal_data.get('leap_year_rule')
        if not leap_year_rule:
            return False
        return eval(leap_year_rule.replace('year', str(year)))
    
    def set_date(self, day=None, month=None, year=None):
        # Allow changing any of the elements of the date
        day = day or self.day
        month = month or self.month
        year = year or self.year

        if not self._date_is_valid(day, month, year):
            return "lol nope" # TODO: raise an exception here

        self.day = day
        self.month = month
        self.year = year
    
    def _date_is_valid(self, day, month, year):
        if month.lower() not in self.cal_data['months']:
            return False
        elif day < 1 or day > self.days_in_month(month, year):
            return False
        return True

    def adjust_date(self, days):
        month_keys = list(self.cal_data['months'].keys())

        if days > 0:   
            while (self.day + days) > self.days_in_month(self.month, self.year):
                # bleed off days to the end of the month
                days -= (self.days_in_month(self.month, self.year) - self.day)

                # move to the next month
                i = month_keys.index(self.month.lower())
                
                # advancing the month would roll over to next year
                if i+1 == len(month_keys):
                    i = -1
                    self.year += 1
                
                new_month = self.cal_data['months'][month_keys[i+1]]['name']

                self.month = new_month
                self.day = 0
            
            self.day += days

        elif days < 0:
            days = abs(days)
            while (self.day - days) < 1:
                # bleed off days to the beginning of the month
                days -= self.day

                # move to the previous month
                i = month_keys.index(self.month.lower())

                # going back a month would roll over to the prior year
                if i-1 < 0:
                    i = 0
                    self.year -= 1
                
                new_month = self.cal_data['months'][month_keys[i-1]]['name']

                self.month = new_month
                self.day = self.days_in_month(self.month, self.year)
            
            self.day -= days

    def days_since_date(self, date_then, date_now):
        days_since = 0

        if date_now.year == date_then.year and \
                date_now.month == date_then.month and \
                date_now.day >= date_then.day:
            days_since += date_now.day - date_then.day
        else:
            # get the days until the end of the year
            days_since += self.days_in_year(date_then.year) - \
                    self.day_of_year(date_then)
            year_diff = date_now.year - date_then.year

            # get days for intervening years
            if year_diff > 1:
                for i in range(1, year_diff):
                    days_since += self.days_in_year(date_then.year + i)
            
            # get elapsed days of current year
            days_since += self.day_of_year(date_now) - 1 # -1 because the day ain't over yet
        
        return days_since

    def day_of_year(self, date):
        day = date.day or self.day
        month = date.month or self.month
        year = date.year or self.year

        if not self._date_is_valid(day, month, year):
            return "lol nope" # TODO: raise an exception here

        day_of_year = 0
        month = month.lower()

        for month_key in self.cal_data['months']:
            if month_key == month:
                day_of_year += day
                break
            else:
                day_of_year += self.days_in_month(month_key, year)

        return day_of_year


# This class is based largely on the awesome Astral library:
# https://github.com/sffjunkie/astral/
# which was great at Earth but not abstract enough for fantasy settings.
class Almanac:

    depression_civil = -6
    depression_nautical = -12
    depression_astronomical = -18

    rising = 1
    setting = -1

    def __init__(self, calendar):
        self.calendar = calendar

        self.minutes_in_hour = calendar.cal_data['minutes_in_hour']
        self.hours_in_day = calendar.cal_data['hours_in_day']
        self.solar_days_in_year = calendar.cal_data['solar_days_in_year']
        self.axial_tilt = calendar.cal_data['axial_tilt']

    def dawn(self, date, latitude, depression=0):
        if not depression:
            depression = self.depression_civil

        try:
            return self.calc_time(depression, self.rising, date, latitude)
        except ValueError:
            # no "dawn" at this latitude on this date
            return None
    
    def sunrise(self, date, latitude):
        try:
            return self.calc_time(-0.833, self.rising, date, latitude)
        except ValueError:
            # no sunrise at this latitude on this date
            return None

    def sunset(self, date, latitude):
        try:
            return self.calc_time(-0.833, self.setting, date, latitude)
        except ValueError:
            # no sunset at this latitude on this date
            return None
    
    def dusk(self, date, latitude, depression=0):
        if not depression:
            depression = self.depression_civil

        try:
            return self.calc_time(depression, self.setting, date, latitude)
        except ValueError:
            # no "dusk" at this latitude on this date
            return None

    def calc_time(self, depression, direction, date, latitude):
        hour_angle = direction * self.hour_angle(depression, date, latitude)
        delta = -hour_angle # longitude would factor in here if we cared
        time_diff = 4 * delta
        noon_minutes = (self.hours_in_day / 2) * self.minutes_in_hour 
        time_utc = noon_minutes + time_diff # - eqtime

        hour = int(time_utc // self.minutes_in_hour)
        minute = int(time_utc % self.minutes_in_hour)
        
        if hour > self.hours_in_day - 1:
            hour -= self.hours_in_day
            day = date.day + 1 #TODO: replace this - need a real "next" date fn
        elif hour < 0:
            hour += self.hours_in_day
            day = date.day - 1 #TODO: replace this - need a real "prev" date fn
        else:
            day = date.day

        return Time(hour, minute), Date(day, date.month, date.year)

    def hour_angle(self, depression, date, latitude):
        declination = self.solar_declination(date)

        # Gotta be in radians for Python's math functions
        alt = math.radians(depression) # altitude of center of solar disc
        latitude = math.radians(latitude)
        declination = math.radians(declination)
        
        cos_hour_angle = (
            (math.sin(alt) - math.sin(latitude) * math.sin(declination)) /
            (math.cos(latitude) * math.cos(declination))
        )
        hour_angle = math.degrees(math.acos(cos_hour_angle))
        return hour_angle
    
    def solar_declination(self, date):
        # Get the solar declination in degrees...

        # Figure out days since the previous winter solstice
        # TODO: this section should be extracted into the Calendar?
        ws = self.calendar.cal_data['seasons']['winter_solstice']
        
        ws_year = date.year \
                if date.month == ws['month'] \
                and date.day >= ws['day'] \
                else date.year - 1

        ws_date = Date(ws['day'], ws['month'].lower(), ws_year)

        days_since_ws = self.calendar.days_since_date(ws_date, date)

        # Figure out how much rotation has happened since the winter solstice
        deg_per_day = 360 / self.solar_days_in_year
        rotation = days_since_ws * deg_per_day

        # Calculate the declination
        declination = -self.axial_tilt * math.cos(math.radians(rotation))

        return declination