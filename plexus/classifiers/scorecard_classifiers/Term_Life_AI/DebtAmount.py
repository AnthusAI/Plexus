from plexus..FastTextClassifier import FastTextClassifier

class DebtAmount(FastTextClassifier):

    def __init__(self):
        super().__init__()
        self.context = """
Mortgages, personal loans, credit cards, financial obligations, financial commitments, debt levels, mortgage details, credit card debt. The total amount of a caller's outstanding debts.
"""

        self.relevant_examples = """
Do you have a mortgage?
How much is your mortgage?
I have a mortgage.
My mortgage debt is significant.
Payments.
Loans.
Financial.
I want this much to cover the mortgage.
Now most people wanna make sure there's life insurance coverage on their policy to take care of major debts like a mortgage
"And so you're looking for that to just take care of your husband and kids if something happens to you, or do you have a mortgage you wanna pay off, or what's the goal for the life insurance.
It would be mortgage and the payoff colleges.
you know, Just covering expenses
the mortgage, replace lost income, that kind of thing?
Okay. A mortgage balance that would be left to each other if you go early?
Okay. And then we've got the mortgage balance.
And then do you guys have a mortgage or any major debt?
Yeah. We got a 527 dollar mortgage
Do you know how many years you have left?
It's been paying about 7 years.
Would she be able to pay the mortgage?
Yeah. So is a hundred thousand going to be enough
then if something happens to you that would only leave a hundred thousand for her to help with the mortgage?
Yeah. Because that that's gonna pay the mortgage off and still have a good little bit
you know, because right now the it's, like, 60 64000 is what's sold on the house.
Oh, I'm sorry. I thought you said 527 on the mortgage.
I was, like, I was thinking, I don't think a hundred thousand is enough for your mortgage.
And and do you have any any major debt right now, like a mortgage, anything like that?
We do have some You know, it's not very much because we own properties and things like that.
Tell me a little bit about what you what what you wanna accomplish with life insurance as far as protecting income or a mortgage or both or if you have kids at home still?
Okay. Do you have any major debt like a mortgage?
Okay. Do you know your mortgage balance?
I owe 90 something.
Okay. So then you wanna probably make sure if something happens to you that she's able to to either pay the mortgage payments or pay off the mortgage or whatever
The reason the reason I'm I'm asking is, you know, typically term life insurance is like I said, it's to replace income, pay debt pay off debt, like, a mortgage, take care of kids.
How many years do you have left on your mortgage?
We want 30 year. You've got 30 years left or 29 left on your mortgage.
Just protecting that income for a spouse or mortgage?
And then when it comes to mortgages, any mortgage debts for you?
Yes. About a hundred and 80000 between the mortgage and a home equity loan.
Okay, so, 180 between mortgage and home equity.
We just wanna make sure that we we cover, you know, mortgage, any debt, and allow my wife to still live.
Based on what you're telling me, I would say, you know, have enough to at least pay off the house
do you have any other debt besides the the home equity and the mortgage?
Yes. We have credit card debt that we have been working for the last 5 years to reduce.
And then any car loans or anything else, personal loans that you would want her to pay?
No personal loans.
So you can always start high, and then as you pay down your mortgage, you can reduce it if you like.
Now what you're eligible for is about 1 and a quarter What is do you have mortgage right now, [NAME_GIVEN_3]? 
So, yeah, the price of the house because I'll help determine what mortgage amount you'll be carrying.
In your position, what you wanna do is cover the mortgage. I was figuring you'd have possibly a quarter million in debt in this up to the mortgage.
Do you have a mortgage you wanna pay off, or is it just to leave your line? 
So if something happened to you, you wanna pay off those 2 mortgages and and leave your wife some extra
Agent: By then, your mortgages are probably paid off, you know, your life's a little bit different.
on a protect book both sides of the house if something happened to her, you'd still have a couple of mortgages and
Do you have a mortgage?
Because it's easier to like a mortgage loan, it's either it's either it's loan, mortgage a like to easier it's Because Period.
I want this much to cover the mortgage.
You know, especially with having those 2 little ones running around in that 250000 dollar mortgage.
the house, also cover that mortgage. And then we have that mortgage there too.
Also cover the mortgage, and then it leaves about 2 and a half years of your income for your wife.
How many years were on that mortgage again, 28? It also covers that mortgage.
And do you have a mortgage still?
And then we have the the mortgage crunch bubble of 2008, right, where everybody thought they had a million dollar home, and then it turned out that it was almost worth nothing.
What is do you have mortgage right now,
So, yeah, the price of the house because I'll help determine what mortgage amount you'll be carrying.
In your position, what you wanna do is cover the mortgage. I was figuring you'd have possibly a quarter million in debt in this up to the mortgage.
Do you have a mortgage?
So I was thinking a million million 2, somewhere right in there.
Agent: So, basically, mortgage protect taking care of, wife and kids, replacing your income if something unexpected happened to you.
And do you guys have a mortgage, or is there anything specific you wanna make sure you could pay off, or is it just income replacement?
Basically, you know, we don't have a mortgage right now.
Do you have a mortgage you wanna pay off, or is it just to leave your line?
What's the balance on the mortgage?
So if something happened to you, you wanna pay off those 2 mortgages and and leave your wife some extra cash?
By then, your mortgages are paid off.
I figure if you want a small policy, maybe even, you know, 02:50 or a hundred thousand just to if we wanna pay off that mortgage something and help me with the rental property if something happens to you.
So we assumed that if if 1 of them 1 of your financial obligations
Do you have a mortgage or any debts that you'd wanna have paid off as something were to happen to you, sir?
The other need and and for them, it's just a up, able to cover that mortgage if that's their inheritance or whatever else they or you might see fit.
And do you have any major debt, mortgage, or anything like that?
Great. And then any major debts, mortgage. Mortgage, if you wanna pay off the mortgage, how much would it be?"
to protect a mortgage or you're not having to protect children, then, you know,
And then when it comes to mortgages, any mortgage debts for you?
Tell me a little bit about what you what what you wanna accomplish with life insurance as far as protecting income or a mortgage or both or if you have kids at home still?
And and do you have any any major debt right now, like a mortgage, anything like that?
We do have some You know, it's not very much because we own properties and things like that.
And then do you guys have a mortgage or any major debt?
Yeah. We got a 527 dollar mortgage
Do you know how many years you have left?
It's been paying about 7 years.
Would she be able to pay the mortgage?
So is a hundred thousand going to be enough
Like, do you guys carry a mortgage you wanna make sure your wife get paid off?
the mortgage, replace lost income, that kind of thing?
A mortgage balance that would be left to each other if you go early?
Okay. And then we've got the mortgage balance.
Now most people wanna make sure there's life insurance coverage on their policy to take care of major debts like a mortgage
I want this much to cover the mortgage.
Just, you know, if something did work where to happened just to cover, you know, balances on mortgages and stuff of that for my wife.
Okay. And mortgage, what what would you say that balance is now, sir?
I did it. So my main mortgage is 02:05, and then I did a ElOC for 1 So about 3 I'd say about 03:30.
So, yeah, you're definitely the bread winner and, you know, don't want her to have to sell the house if something happens to you or struggle greatly to pay that mortgage.
And Most people also wanna make sure there's enough coverage as well to take care of any major debts that leave behind, like, a mortgage.
"""

        self.irrelevant_examples = """
Hello?
Hey, mister Nelson. This is Kyle Thompson with SelectQuote on a recorded line. How are you doing today?
Real good. How are you?
I am doing fine. Thanks for asking.
I was just reaching out regards to the life insurance request that we received from you.
Was it you who filled out all the information online for us to reach out for you?
Yes. It was. What is your name, Kyle what?
Okay.
Kyle Thompson.
Allison? Okay. Could I get your number just in case?
But right this minute, I'm waiting to back hear back from Delta Airlines.
I'm trying to schedule our pet to fly with me, and they said they'd call me back and I haven't.
Let me give you my number, and that way you can get everything situated.
And then I could put a note to maybe reach back out to you later on this evening, or you can me a call, we can just kinda jump in where we left
Yeah.
Okay. And okay. Your number?
And after you dial my number, if you hit extension 1 at the end, it's not really an extension, but it skips, like, all the automated talking that pops up when you call in.
It'll just send you straight to me. Okay?
We could talk or go over stuff because they might not call back for an hour. I don't know what they'll do.
They're very slow.
Not a problem. Well, how about this?
What I can do is I'm just gonna kinda get some preliminary information out of the way, kind of the qualifying information, and kinda just give you a little bit of information about us.
And because I do actually I was calling to to see if there was a good time for me to reach back out because I actually do have an appointment coming up here in a few minutes as well.
But we can at least get a chunk of it knocked out for you here. Okay?
Okay. That's correct.
Right. Now I did see that you put online looks like currently don't have any life insurance. Is that correct?
It's Okay.
He's 1 year older than me.
I have never checked on on, like, life insurance my whole life.
And so it's like I'm really coming into this, not knowing what to expect, and kinda learning things in an organic manner where everybody I'm talking to has been in the industry for years.
So it's like they know things, and there are certain things that are really obvious to them, and it's not obvious to me because I haven't dealt with it at all.
So I'm just kinda feeling my way through, and I've learned a lot just And I've checked with a couple of companies in the last few days, so I'm kinda learning fast.
Well, yeah, we wouldn't be able to to get a whole lot done with you anyway just to legal purposes, I would need to actually have him on the line to get it set up. But what I can do is,
Okay. like I said, is I can just kinda get some basic information.
That that way, I can at least give you a rough estimate of what the rates might look like for them for you guys.
Okay?
Sure.
Yeah.
And he would obviously find everything, and he asked me to actually look this stuff up for him.
Alright.
Well, just to give you information.
He's just really soft spoken.
Well, have you ever worked or gotten any quotes with us here at SelectQuote in the past, or is this your first time or reaching out to us?
It's the first time reaching out, but, I mean, I don't know if sure.
My understanding is you're a broker, so you deal with different companies.
So I may have spoken to, you know, a company that that you folks deal with.
Yeah. I mean, we're the the oldest and largest term insurance brokers in the country.
I mean, we monitor over 400 different insurance companies each year, but we do work with just the top a and a plus rated carriers.
And so, essentially, I would just be shopping all of those companies to find the lowest rate available specific specifically for Irving just because every insurance company.
Right.
It's definitely something that the insurance companies are all gonna rate differently.
He's a light smoker, but, yeah, he does.
Whatever company this is this is what happened the other the other day.
Last Friday, I was talking to a State Farm agent, and he he said that they didn't really think Erwin would qualify, but he wanted me to fill out the paperwork.
And I just told him if you're not gonna deal with my brother, I'm not gonna deal with you because I'm actually super healthy.
I don't smoke or drink or nothing.
I haven't had any health issues.
I thought you take it good with the bad.
Okay? He's risky.
I'm not I'm not you want my business?
Take his business.
Yeah.
I'm also looking for a company that I can deal with too.
We'll definitely make sure that we I mean, that's just 1 of the advantages of working with us since we work with someone carriers.
I mean, I mean, there's carriers that we do work with that could potentially decline and that, hopefully, you know, carriers that he'll have some options available with as well.
Right.
How many strokes has he had?
Well, what the deal is?
First off, I think it'd be really I wanna have solid insurance.
So I would hope I don't know if you don't ever get in touch with the primary care physician, but you folks would certainly be welcome to his medical information. But what happened was he had a series of really small strokes.
He didn't have 1 big he didn't have 1 big stroke.
And there was a reason they could tell the difference.
But no. They were not TIAAs, but they were small strokes.
And I and he said a number of them, and I said, you mean between you know, 5 and 10, and he said, oh, we have no idea.
And that was a male a doctor at the Mayo Clinic.
So I I was dealing with the best of the best far as doctors.
And, I mean, to be completely honest with you, most of them are gonna have a postponement period period of at least a year, but I'm going and double checking for you just to make sure.
Okay. That's something I honestly didn't know that.
I know that even dealing with Social Security, I I want to check to see if he would get Social Security disability because nobody in our family we don't have a big family that networks where they all learn stuff and they know.
We're like these people we're on our own, you know, just a small family.
The highest that he would be able to get on something like that that doesn't have any sort of medical underwriting would be 25000.
Those don't go through any sort of medical underwriting either, but, of course, that would just pay the death benefit if you were to die from an accident or, like, some sort of injuries that were sustained from an dent.
But since those are just accidental, those rates are typically pretty inexpensive for those types of policies.
So I mean, if that's something you're interested in, I can definitely get that number pulled up and see what it might look like for an accidental policy for him.
Either that, or you could fax information or, I mean, email it or send something
and, you know, I have your contact number attached to it so you get credit for it.
You know?
Yeah.
I think the only thing that they have that they can email for those is, like, a brochure, but it doesn't really have the the numbers in there.
It just has some information about the actual policy, but I can pull it up for you in about 10 seconds.
Okay? Or wanting me to look at, like, the same coverage amount, like, the 02:50 for an accidental policy?
If that's something that he could do.
And like I said, I'm gonna I'm gonna plan on getting coverage for both of us.
Well, maybe the accidental policy is not available in Minnesota.
Give me 1 moment.
And we don't.
Have a problem with waiting, you know, 6 months.
There's no fire.
I don't expect them to tip over Yeah.
What?
in Minnesota or Massachusetts.
So he probably would just have to go with 1 of those guaranteed issues of smaller policies.
Okay. Great. Alright.
Alright. We have a great rest of your day, and I will talk to you soon.
Yep. Thank you, sir. Thanks,
Thanks.
Michael.
Bye bye.
Bye.
You're welcome. Bye bye.
Is [NAME_GIVEN_1] Bank available?
Speaking.
Hey. This is [NAME_GIVEN_2] Stevens on a recorded line from SelectQuote.
I was up with you on your request for the life insurance rates.
Yes.
How are you today?
Oh, yeah. I'm okay.
Did I get you an okay time to go over that?
Yeah. I got a few minutes Alright.
Okay.
So I have the information you submitted on the website.
Appreciate you taking the time to do that.
Again, my name is [NAME_GIVEN_2] Stevens.
I'm a licensed agent in New Mexico from SelectQuote Insurance.
And, basically, what I wanna do is just confirm that health information that you provided.
That'll give me a head start to the shopping process, which is what we do for you.
We're gonna 0 in on which a plus companies are gonna be fit and have the lowest rates for you. Okay?
Alright. Yes.
Your date of birth, [DOB_1].
Okay.
And you indicated you don't currently have existing life insurance coverage now?
I don't.
I don't know if it's life insurance.
It's just through a over for securitas.
Okay. So, like, a little final expense policy, if something happened
to
Yeah.
you, that just
Yeah.
kinda does a variable cost?
My children.
Okay. And what are you trying to protect with additional term insurance? Just protecting that income for a spouse or mortgage? Or what? Kids.
Yes.
So you're not currently married.
No.
But if something happened to you, you'd have some kids you wanna make sure they're taken care of.
"""

